#!/usr/bin/env python3
"""Flag observations using joint position/intensity evidence; optionally filter unscaled data."""
import argparse
import csv
import numpy as np
from dials_common import load_pair, new_output, pair_provenance, write_json


def screen(groups, datasets, intensity, variance, usable, strong, xy_error,
           xy_min, z_min, min_references, min_datasets):
    """Leave the whole tested dataset out; guard Z with between-observation scatter."""
    z = np.full(len(groups), np.nan)
    reference_count = np.zeros(len(groups), dtype=int)
    dataset_count = np.zeros(len(groups), dtype=int)
    order = np.argsort(groups)
    partitions = np.split(order, np.flatnonzero(np.diff(groups[order])) + 1)
    for indices in partitions:
        indices = indices[usable[indices]]
        for dataset in np.unique(datasets[indices]):
            targets = indices[datasets[indices] == dataset]
            refs = indices[datasets[indices] != dataset]
            distinct = len(np.unique(datasets[refs]))
            reference_count[targets] = len(refs)
            dataset_count[targets] = distinct
            if len(refs) < min_references or distinct < min_datasets:
                continue
            median = np.median(intensity[refs])
            mad = 1.4826 * np.median(np.abs(intensity[refs] - median))
            denominator = np.sqrt(variance[targets] + max(mad**2, np.median(variance[refs])))
            z[targets] = (intensity[targets] - median) / denominator
    candidate = usable & strong & (xy_error > xy_min) & (np.abs(z) > z_min)
    return candidate, z, reference_count, dataset_count


def observation_key(identifier, hkl, xyz):
    return (identifier, *map(int, hkl), *[round(float(value), 5) for value in xyz])


def map_candidates(candidate_keys, source_keys):
    """Require a bijection: do not silently remove duplicate or changed predictions."""
    from collections import Counter
    counts = Counter(source_keys)
    invalid = {key: counts[key] for key in candidate_keys if counts[key] != 1}
    if invalid:
        raise ValueError(f"Candidate mapping incomplete or ambiguous: {len(invalid)} keys")
    return np.array([key in candidate_keys for key in source_keys], dtype=bool)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expt", required=True, help="Scaled experiments")
    parser.add_argument("--refl", required=True, help="Scaled unmerged reflections")
    parser.add_argument("--out", required=True)
    parser.add_argument("--d-min", type=float, required=True)
    parser.add_argument("--partiality", type=float, required=True)
    parser.add_argument("--friedel", choices=["merge", "separate"], required=True)
    parser.add_argument("--xy-min", type=float, required=True, help="Pixels; justified for the current data")
    parser.add_argument("--z-min", type=float, required=True)
    parser.add_argument("--min-references", type=int, required=True)
    parser.add_argument("--min-datasets", type=int, required=True)
    parser.add_argument("--source-expt", help="Original unscaled experiments, same indexing basis")
    parser.add_argument("--source-refl", help="Original unscaled integrated observations")
    parser.add_argument("--write-filtered", action="store_true", help="Write a trial, not an adopted selection")
    args = parser.parse_args()
    if min(args.d_min, args.xy_min, args.z_min) <= 0 or not 0 <= args.partiality <= 1:
        parser.error("Invalid positive threshold or partiality")
    if args.min_references < 2 or args.min_datasets < 2:
        parser.error("At least two independent reference datasets and observations are required")
    if args.write_filtered and not (args.source_expt and args.source_refl):
        parser.error("--write-filtered requires the original unscaled pair")
    from cctbx import crystal, miller
    from dials.array_family import flex
    experiments, table, lookup, _ = load_pair(args.expt, args.refl)
    required = ["inverse_scale_factor", "intensity.scale.value", "intensity.scale.variance",
                "partiality", "xyzobs.px.value", "xyzcal.px", "miller_index"]
    if any(column not in table for column in required):
        raise ValueError("Scaled unmerged table lacks required intensity or position columns")
    dataset = np.asarray(table["id"])
    g = np.asarray(table["inverse_scale_factor"])
    with np.errstate(divide="ignore", invalid="ignore"):
        intensity = np.asarray(table["intensity.scale.value"]) / g
        variance = np.asarray(table["intensity.scale.variance"]) / g**2
    sym = crystal.symmetry(unit_cell=experiments[0].crystal.get_unit_cell(),
                           space_group=experiments[0].crystal.get_space_group())
    ms = miller.set(sym, indices=table["miller_index"], anomalous_flag=args.friedel == "separate")
    _, groups = np.unique(np.asarray(ms.map_to_asu().indices()), axis=0, return_inverse=True)
    xy_error = np.linalg.norm(np.asarray(table["xyzobs.px.value"])[:, :2] -
                              np.asarray(table["xyzcal.px"])[:, :2], axis=1)
    usable = (~np.asarray(table.get_flags(table.flags.bad_for_scaling, all=False)) &
              np.isfinite(g) & (g > 0) & np.isfinite(intensity) & np.isfinite(variance) &
              (variance > 0) & (np.asarray(table["partiality"]) >= args.partiality) &
              (np.asarray(ms.d_spacings().data()) >= args.d_min))
    candidate, z, nref, ndataset = screen(groups, dataset, intensity, variance, usable,
                 np.asarray(table.get_flags(table.flags.strong)), xy_error,
                 args.xy_min, args.z_min, args.min_references, args.min_datasets)
    selected = np.flatnonzero(candidate)
    report = {"inputs": pair_provenance(args.expt, args.refl), "parameters": vars(args),
              "rows": len(table), "usable_rows": int(usable.sum()), "candidate_count": len(selected),
              "scope": "Joint-evidence diagnostic candidates, not automatic rejection. Whole tested dataset excluded from reference; weak or negative intensity alone is not a criterion.",
              "filtered_written": False}
    filtered = source_experiments = None
    if args.write_filtered:
        source_experiments, source, source_lookup, _ = load_pair(args.source_expt, args.source_refl)
        if "intensity.scale.value" in source or "inverse_scale_factor" in source:
            raise ValueError("Source is already scaled; supply the original integrated table")
        source_ids = np.asarray(source["id"])
        candidate_keys = [observation_key(lookup[int(dataset[k])], table["miller_index"][int(k)],
                           table["xyzcal.px"][int(k)]) for k in selected]
        if len(set(candidate_keys)) != len(candidate_keys):
            raise ValueError("Duplicate candidate keys; cannot identify individual observations")
        source_keys = [observation_key(source_lookup[int(source_ids[k])], source["miller_index"][k],
                                      source["xyzcal.px"][k]) for k in range(len(source))]
        drop = map_candidates(set(candidate_keys), source_keys)
        filtered = source.select(flex.bool((~drop).tolist()))
        report.update({"unscaled_source": pair_provenance(args.source_expt, args.source_refl),
                       "mapped_count": int(drop.sum()), "remaining_rows": len(filtered),
                       "filtered_written": True})
    out = new_output(args.out)
    with (out / "candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scaled_row", "identifier", "dataset_id", "h", "k", "l", "x", "y", "z",
                         "scaled_I", "scaled_sigma", "xy_error_px", "robust_Z", "reference_count", "reference_datasets"])
        for k in selected:
            row = int(k)
            writer.writerow([row, lookup[int(dataset[row])], int(dataset[row]), *table["miller_index"][row],
                             *table["xyzcal.px"][row], float(intensity[row]), float(np.sqrt(variance[row])),
                             float(xy_error[row]), float(z[row]), int(nref[row]), int(ndataset[row])])
    if filtered is not None:
        filtered.as_file(str(out / "filtered.refl"))
        source_experiments.as_file(str(out / "filtered.expt"))
    write_json(out / "screening_audit.json", report)
    print(f"{len(selected)} diagnostic candidates; filtered trial written: {filtered is not None}")


if __name__ == "__main__":
    main()
