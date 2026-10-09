#!/usr/bin/env python3
"""Dataset mapping, geometry residuals and diagnostic equivalent-intensity agreement."""
import argparse
import numpy as np
from dials_common import load_pair, dataset_records, pair_provenance, new_output, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expt", required=True)
    parser.add_argument("--refl", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--d-min", type=float, required=True)
    parser.add_argument("--partiality", type=float, required=True)
    parser.add_argument("--friedel", choices=["merge", "separate"], required=True)
    args = parser.parse_args()
    if args.d_min <= 0 or not 0 <= args.partiality <= 1:
        parser.error("d-min must be positive and partiality between 0 and 1")
    experiments, table, lookup, groups = load_pair(args.expt, args.refl)
    records = dataset_records(experiments, groups)
    ids = np.asarray(table["id"])
    if "xyzobs.px.value" in table and "xyzcal.px" in table:
        xy = np.asarray(table["xyzobs.px.value"])[:, :2] - np.asarray(table["xyzcal.px"])[:, :2]
        for record in records:
            selected = xy[ids == record["dataset_id"]]
            valid = selected[np.all(np.isfinite(selected), axis=1)]
            record["geometry_rows"] = len(valid)
            record["xy_rms_px"] = np.sqrt(np.mean(valid**2, axis=0)).tolist() if len(valid) else None
    if "intensity.scale.value" in table:
        from dials.util.filter_reflections import filter_reflection_table
        from cctbx import crystal, miller
        filtered = filter_reflection_table(table.select(table["id"] >= 0), intensity_choice=["scale"],
                    partiality_threshold=args.partiality, combine_partials=True,
                    min_isigi=-999, d_min=args.d_min)
        if len(filtered) == 0:
            raise ValueError("No usable scaled observations")
        sym = crystal.symmetry(unit_cell=experiments[0].crystal.get_unit_cell(),
                               space_group=experiments[0].crystal.get_space_group())
        indices = miller.set(sym, indices=filtered["miller_index"],
                    anomalous_flag=args.friedel == "separate").map_to_asu().indices()
        _, inv = np.unique(np.asarray(indices), axis=0, return_inverse=True)
        values = np.asarray(filtered["intensity.scale.value"])
        variance = np.asarray(filtered["intensity.scale.variance"])
        counts = np.bincount(inv)
        means = np.bincount(inv, weights=values) / counts
        deviation = np.abs(values - means[inv])
        fids = np.asarray(filtered["id"])
        for record in records:
            select = (fids == record["dataset_id"]) & (counts[inv] > 1)
            denominator = float(values[select].sum())
            record.update({"observations_with_equivalents": int(select.sum()),
                "mean_I_over_sigma": float(np.mean(values[select]/np.sqrt(variance[select]))) if select.any() else None,
                "diagnostic_deviation_ratio": float(deviation[select].sum()/denominator) if denominator > 0 else None})
    out = new_output(args.out)
    write_json(out / "dataset_audit.json", {"inputs": pair_provenance(args.expt, args.refl),
        "selection": vars(args), "datasets": records,
        "scope": "Diagnostic contributions to a global unweighted equivalent mean, not official per-scan Rint. Requires a common indexing basis. No automatic deletion."})
    print(f"Audited {len(records)} experiments; wrote {out / 'dataset_audit.json'}")


if __name__ == "__main__":
    main()
