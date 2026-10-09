#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Submit checkCIF, record actual mode/input hashes, and create evidence-free VRF drafts.
Network fallback may produce CIF-only validation; inspect the saved report.
"""
import os, re, sys, html, uuid, ssl, time, json, argparse, urllib.request
import urllib.parse, http.cookiejar

URL = 'https://checkcif.iucr.org/cgi-bin/checkcif_hkl.pl'


def build_body(files, fields):
    b = uuid.uuid4().hex
    body = b''
    for k, v in fields.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, path in files.items():
        data = open(path, 'rb').read()
        body += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; '
                 f'filename="{os.path.basename(path)}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n').encode()
        body += data + b'\r\n'
    body += f'--{b}--\r\n'.encode()
    return b, body


def html_to_text(s):
    s = re.sub(r'(?is)<script.*?</script>', '', s)
    s = re.sub(r'(?is)<style.*?</style>', '', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|tr|h1|h2|h3|li|pre)>', '\n', s)
    s = re.sub(r'(?i)</t[dh]>', ' | ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'[ \t]+', ' ', s)
    return re.sub(r'\n\s*\n+', '\n\n', s)


def parse_alerts(page_html):
    """返回 [(test, level, text)]，level ∈ A/B/C/G。

    checkCIF 的报告里 ALERT 标识常被 HTML 标签拆开，例如
        <a ...>PLAT340_ALERT_3_</a><a ...>B</a>&nbsp; Low Bond Precision ...
    所以先剥标签再按文本解析最稳。
    """
    txt = html_to_text(page_html)
    out, seen = [], set()
    # 1) 主模式：TEST_ALERT_n_L <说明>
    for m in re.finditer(r'([A-Z][A-Z0-9]*_ALERT_\d+_([ABCG]))\b([^\n]{0,240})', txt):
        t, lv, tx = m.group(1), m.group(2), m.group(3)
        tx = re.sub(r'^\s*[|:]?\s*', '', tx).strip()
        if (t, tx) not in seen:
            seen.add((t, tx))
            out.append((t, lv, tx))
    # 2) 兜底：只出现级别行（Alert level A 段）时，从该段抓取
    if not out:
        for m in re.finditer(r'([A-Z][A-Z0-9]*_ALERT_\d+)\s*_?\s*([ABCG])\b([^\n]{0,200})', txt):
            t, lv, tx = m.group(1) + '_' + m.group(2), m.group(2), m.group(3)
            if (t, tx) not in seen:
                seen.add((t, tx))
                out.append((t, lv, tx.strip()))
    return out


def submit(cif, fcf=None, valid='checkcif_only', tries=4, verbose=True):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0'),
                         ('Referer', 'https://checkcif.iucr.org/')]
    fields = {'from_index': 'from_index', 'runtype': 'symmonly',
              'referer': 'checkcif_server', 'outputtype': 'HTML',
              'validtype': valid, 'valout': 'vrfabc', 'duplic': 'duplicno',
              'UPLOAD': 'Send CIF for checking'}
    files = {'filecif': cif}
    if fcf:
        files['filefcf'] = fcf
    b, body = build_body(files, fields)
    if verbose:
        print(f"提交 {os.path.basename(cif)}"
              f"{(' + ' + os.path.basename(fcf)) if fcf else ''}  "
              f"[{valid}]  {len(body):,} 字节")
    req = urllib.request.Request(URL, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={b}')
    try:
        r = opener.open(req, timeout=180)
        page = r.read().decode('utf-8', 'replace')
        last_url = r.geturl()
    except Exception as e:
        return None, None, f'提交失败: {e}'
    if verbose:
        print(f"  HTTP 首次响应 {len(page):,} 字节")
    best = page
    for k in range(tries):
        if len(page) > 2500 and ('ALERT' in page or 'syntax' in page.lower()
                                 or 'Validation' in page):
            break
        if 'Upload error' in page:
            return page, last_url, '上传被拒（服务器报 Upload error）'
        time.sleep(6)
        try:
            page = opener.open(last_url, timeout=180).read().decode('utf-8', 'replace')
            if verbose:
                print(f"  轮询 {k+1}: {len(page):,} 字节")
            if len(page) > len(best):
                best = page
        except Exception as e:
            if verbose:
                print(f"  轮询 {k+1} 失败: {e}")
    if 'Upload error' in best or not re.search(r'checkCIF/PLATON|No syntax errors found|Syntax problems', html_to_text(best), re.I):
        return best, last_url, '未获得可识别的验证报告（可能上传失败或尚未完成）'
    return best, last_url, None


def submit_with_fallback(cif, fcf=None, valid=None, verbose=True):
    """先按用户指定的 validtype 提交；失败则自动降级到 checkcif_only。

    实测：同时上传 CIF + FCF 时服务器常报 "Upload error"，
    而只上传 CIF（checkcif_only）稳定成功。故内置依次回退。
    """
    tries = []
    if fcf:
        tries.append(('checkcif_with_hkl', fcf))
    tries.append(('checkcif_only', None))
    if valid:                                  # 用户显式指定时优先，但仍保留回退
        tries = [(valid, fcf if valid != 'checkcif_only' else None)] + \
                [t for t in tries if t[0] != valid]
    last = (None, None, '未提交')
    for vt, f in tries:
        page, url, err = submit(cif, f, valid=vt, verbose=verbose)
        if err is None:
            if vt != (valid or tries[0][0]):
                print(f"  → 已回退到 {vt} 并成功")
            return page, url, None, vt
        print(f"  !! {vt} 失败：{err}")
        last = (page, url, err)
    return last[0], last[1], last[2], tries[-1][0]


def make_vrf(alerts, block='structure'):
    lines = ['# DRAFT ONLY: replace each response with verified, case-specific evidence.', '']
    grouped = {}
    for test, lv, text in alerts:
        if lv not in 'ABC':
            continue
        grouped.setdefault(test, []).append(text)
    for test, descriptions in grouped.items():
        text = ' | '.join(descriptions)
        lines += [f'_vrf_{test}_{block}', ';', f'PROBLEM: {text}',
                  'RESPONSE: TODO - Record observations, file/atom/reflection identifiers,',
                  'tests performed, result, and remaining limitations. No conclusion is assumed.', ';']
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cif', required=True)
    ap.add_argument('--fcf')
    ap.add_argument('--outdir')
    ap.add_argument('--valid', default=None,
                    choices=['checkcif_only', 'checkcif_with_hkl',
                             'iucr_checkcif_with_hkl'])
    ap.add_argument('--vrf', action='store_true', help='生成 VRF 回复模板')
    ap.add_argument('--block', default='structure', help='CIF datablock 名（VRF 用）')
    ap.add_argument('--no-net', action='store_true', help='只看本地文件大小，不联网')
    a = ap.parse_args()

    sz = os.path.getsize(a.cif)
    print(f"CIF: {os.path.basename(a.cif)}  {sz:,} 字节")
    if sz > 150_000:
        print('Large CIF: try the complete file first; inspect server response if upload fails.')
    if a.no_net:
        return

    outdir = a.outdir or os.path.join(os.path.dirname(os.path.abspath(a.cif)), 'validation')
    os.makedirs(outdir, exist_ok=False)
    valid = a.valid
    page, url, err, used = submit_with_fallback(a.cif, a.fcf, valid=valid)
    print(f"（实际使用的 validation type：{used}）")

    if page is None:
        print("!! " + str(err))
        raise SystemExit(2)
    hp = os.path.join(outdir, 'checkcif_report.html')
    open(hp, 'w', encoding='utf-8').write(page)
    txt = html_to_text(page)
    tp = os.path.join(outdir, 'checkcif_report.txt')
    open(tp, 'w', encoding='utf-8').write(txt)
    print(f"已保存 {hp} / {tp}")

    import hashlib
    from datetime import datetime, timezone
    manifest = dict(time_utc=datetime.now(timezone.utc).isoformat(),
                    requested=valid or ('checkcif_with_hkl' if a.fcf else 'checkcif_only'),
                    actual=used, error=err, response_url=url,
                    structure_factor_validation='requires confirmation from report',
                    cif_sha256=hashlib.sha256(open(a.cif, 'rb').read()).hexdigest(),
                    fcf_sha256=hashlib.sha256(open(a.fcf, 'rb').read()).hexdigest() if a.fcf else None)
    if used == 'checkcif_only':
        manifest['structure_factor_validation'] = 'not performed'
        print('PARTIAL: CIF-only check; structure factors were not validated.')
    json.dump(manifest, open(os.path.join(outdir, 'validation_manifest.json'), 'w'), indent=2)
    if err:
        raise SystemExit('Validation failed: ' + str(err))
    if 'No syntax errors found' in txt:
        print("CIF 语法：No syntax errors found")
    elif 'syntax' in txt.lower() and 'ERROR' in txt:
        print("!! CIF 有语法错误，见报告的 Syntax problems 段")
        for m in re.finditer(r'ERROR:[^\n]{0,160}', txt):
            print("   " + m.group(0))

    alerts = parse_alerts(page)
    lv_count = {}
    for t, lv, _ in alerts:
        lv_count[lv] = lv_count.get(lv, 0) + 1
    print(f"\nALERT 统计: " + "  ".join(f"{k}={v}" for k, v in sorted(lv_count.items())))
    print(f"{'test':34}{'lv':>3}  说明")
    print("-" * 104)
    for t, lv, tx in alerts:
        print(f"{t[:33]:34}{lv:>3}  {tx[:60]}")

    # 结构因子报告链接
    m = re.search(r'href="(//checkcif[^"]+/ckf\.html)"', page)
    if m:
        try:
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                             urllib.request.HTTPSHandler(
                                                 context=ssl.create_default_context()))
            op.addheaders = [('User-Agent', 'Mozilla/5.0')]
            sf = op.open('https:' + m.group(1), timeout=90).read().decode('utf-8', 'replace')
            open(os.path.join(outdir, 'structure_factor_report.html'), 'w',
                 encoding='utf-8').write(sf)
            print("\n已下载结构因子报告 structure_factor_report.html")
        except Exception as e:
            print(f"\n结构因子报告下载失败: {e}")

    if a.vrf:
        v = make_vrf(alerts, block=a.block)
        vp = os.path.join(outdir, 'validation_response_form.txt')
        open(vp, 'w', encoding='utf-8').write(v)
        json.dump([{'test': t, 'level': lv, 'text': tx} for t, lv, tx in alerts],
                  open(os.path.join(outdir, 'checkcif_alerts.json'), 'w',
                       encoding='utf-8'), indent=2, ensure_ascii=False)
        print(f"\n已生成 VRF 模板：{vp}")
        print("（仅为待填写草稿；逐条查证后才能用于 CIF 回复）")


if __name__ == '__main__':
    main()
