#!/usr/bin/env python3
"""Verify physical-model components and report absorption-only relative factor limits."""
import argparse
import numpy as np
from dials_common import load_pair, pair_provenance, new_output, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expt", required=True)
    parser.add_argument("--refl", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--partiality", type=float, required=True)
    args = parser.parse_args()
    if not 0 <= args.partiality <= 1:
        parser.error("partiality must be between 0 and 1")
    from dials.algorithms.scaling.scaling_utilities import calc_crystal_frame_vectors, align_axis_along_z
    from dials.command_line.scale import phil_scope
    from dials.util.version import dials_version
    experiments, table, _, groups = load_pair(args.expt, args.refl)
    params = phil_scope.extract()
    records, all_factors = [], []
    for experiment in experiments:
        model = experiment.scaling_model
        if model is None or getattr(model, "id_", None) != "physical":
            raise ValueError("Only the DIALS physical scaling model is supported")
        if "absorption" not in model.components:
            raise ValueError("No absorption component; cannot fabricate transmission limits")
        part = table.select(table["id"] == groups[experiment.identifier])
        suitable = ~(part.get_flags(part.flags.excluded_for_scaling) |
                     part.get_flags(part.flags.user_excluded_in_scaling))
        part = calc_crystal_frame_vectors(part.select(suitable), experiment)
        for name in ("s0c", "s1c"):
            part[name] = align_axis_along_z((1.0, 0.0, 0.0), part[name])
        # This convention matches the tested DIALS 3.30 SingleScalerFactory.
        # Internal API changes must be investigated if the product check fails.
        model.configure_components(part, experiment, params)
        good = ~np.asarray(part.get_flags(part.flags.bad_for_scaling, all=False))
        good &= np.asarray(part["partiality"]) >= args.partiality
        product = np.ones(len(part))
        absorption = None
        for name, component in model.components.items():
            component.update_reflection_data()
            factors = np.asarray(component.calculate_scales())
            product *= factors
            if name == "absorption":
                absorption = factors
        stored = np.asarray(part["inverse_scale_factor"])
        good &= np.isfinite(stored) & (stored > 0)
        if not good.any() or not np.all(np.isfinite(absorption[good]) & (absorption[good] > 0)):
            raise ValueError("No valid positive absorption factors")
        error = float(np.max(np.abs(product[good]/stored[good] - 1)))
        if not np.isfinite(error) or error >= 1e-8:
            raise ValueError(f"Component product does not reproduce applied scaling: {error}")
        values = absorption[good]
        all_factors.append(values)
        records.append({"identifier": experiment.identifier, "dataset_id": groups[experiment.identifier],
                        "observations": len(values), "minimum": float(values.min()),
                        "maximum": float(values.max()), "product_relative_error": error})
    factors = np.concatenate(all_factors)
    out = new_output(args.out)
    write_json(out / "absorption_factors.json", {"inputs": pair_provenance(args.expt, args.refl),
        "dials_version": dials_version(), "partiality": args.partiality, "datasets": records,
        "factor_min": float(factors.min()), "factor_max": float(factors.max()),
        "relative_T_min": float(factors.min()/factors.max()), "relative_T_max": 1.0,
        "scope": "Absorption-only empirical factors with one common maximum normalization. Absolute physical transmission is unknown. Overall scale and decay are excluded. Review conventions and CIF reporting before use; this script never edits CIF."})
    print(f"Verified absorption-only factors; wrote {out / 'absorption_factors.json'}")


if __name__ == "__main__":
    main()
