"""DIALS identifier validation and input provenance; import DIALS only on demand."""
import json
from pathlib import Path
from dials_stage import fingerprint


def load_pair(expt, refl):
    from dxtbx.model.experiment_list import ExperimentListFactory
    from dials.array_family import flex
    experiments = ExperimentListFactory.from_json_file(str(expt), check_format=False)
    table = flex.reflection_table.from_file(str(refl))
    lookup = dict(table.experiment_identifiers())
    identifiers = [experiment.identifier for experiment in experiments]
    if not identifiers or any(not identifier for identifier in identifiers):
        raise ValueError("All experiments must have nonempty identifiers")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate experiment identifiers")
    if len(set(lookup.values())) != len(lookup) or set(identifiers) != set(lookup.values()):
        raise ValueError("Reflection/experiment identifier mapping is incomplete or ambiguous")
    observed_ids = set(table["id"])
    if any(dataset < 0 or lookup.get(dataset) not in identifiers for dataset in observed_ids):
        raise ValueError("Unassigned/mismatched reflection identifiers; repair the pair first")
    groups = {identifier: dataset for dataset, identifier in lookup.items()}
    for experiment in experiments:
        if experiment.crystal is None:
            raise ValueError("Experiments lack crystal models")
    if len({experiment.crystal.get_space_group().type().hall_symbol() for experiment in experiments}) != 1:
        raise ValueError("Different space groups; resolve symmetry/basis before comparison")
    return experiments, table, lookup, groups


def dataset_records(experiments, groups):
    records = []
    for experiment in experiments:
        imageset = experiment.imageset
        template = imageset.get_template() if imageset and hasattr(imageset, "get_template") else None
        records.append({"identifier": experiment.identifier, "dataset_id": groups.get(experiment.identifier),
                        "template": template,
                        "image_range": list(experiment.scan.get_image_range()) if experiment.scan else None,
                        "unit_cell": list(experiment.crystal.get_unit_cell().parameters()),
                        "space_group": experiment.crystal.get_space_group().type().hall_symbol()})
    return records


def new_output(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def pair_provenance(expt, refl):
    from dials.util.version import dials_version
    return {"experiments": fingerprint(expt), "reflections": fingerprint(refl),
            "dials_version": dials_version()}
