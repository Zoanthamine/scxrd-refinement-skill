"""Validate one ligand; optional derived reference geometry is not experimental data."""
import argparse
import hashlib
import json
from pathlib import Path

def prepare(source, output, report, optimize=False, seed=0, max_iters=1000):
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem, rdMolDescriptors
    source=Path(source).resolve(strict=True)
    output=Path(output).resolve(); report=Path(report).resolve()
    if len({source,output,report}) != 3:
        raise ValueError('Source, output and report must be separate files')
    if output.exists() or report.exists():
        raise FileExistsError('Choose new output/report paths')
    if output.suffix.lower() != '.mol':
        raise ValueError('Derived reference output must use .mol')
    if source.suffix.lower()=='.sdf':
        entries=list(Chem.SDMolSupplier(str(source),removeHs=False))
        if len(entries)!=1 or entries[0] is None:
            raise ValueError('SDF must contain exactly one valid record; select the intended ligand explicitly')
        mol=entries[0]
    elif source.suffix.lower()=='.mol':
        mol=Chem.MolFromMolFile(str(source),removeHs=False)
    elif source.suffix.lower()=='.mol2':
        mol=Chem.MolFromMol2File(str(source),removeHs=False)
    else:
        raise ValueError('Supported inputs: MOL, SDF, MOL2')
    if mol is None: raise ValueError('Cannot parse/sanitize ligand')
    Chem.AssignStereochemistry(mol,cleanIt=True,force=True)
    fragments=Chem.GetMolFrags(mol)
    status=None; ff=None
    if optimize:
        if len(fragments)!=1:
            raise ValueError('Optimize one connected ligand at a time; preserve salts as topology evidence')
        mol=Chem.AddHs(mol); mol.RemoveAllConformers()
        params=AllChem.ETKDGv3(); params.randomSeed=seed
        if AllChem.EmbedMolecule(mol,params)!=0: raise ValueError('Embedding failed')
        if AllChem.MMFFHasAllMoleculeParams(mol):
            ff='MMFF94s'; status=AllChem.MMFFOptimizeMolecule(mol,mmffVariant=ff,maxIters=max_iters)
        elif AllChem.UFFHasAllMoleculeParams(mol):
            ff='UFF'; status=AllChem.UFFOptimizeMolecule(mol,maxIters=max_iters)
        else: raise ValueError('No complete MMFF/UFF parameters; use topology-only mode')
        if status!=0: raise ValueError(f'{ff} did not converge; no reference output written')
    result=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                output=str(output),rdkit_version=rdBase.rdkitVersion,
                formula=rdMolDescriptors.CalcMolFormula(mol),formal_charge=Chem.GetFormalCharge(mol),
                heavy_atoms=mol.GetNumHeavyAtoms(),bonds=mol.GetNumBonds(),fragments=len(fragments),
                smiles=Chem.MolToSmiles(Chem.RemoveHs(mol),isomericSmiles=True),
                chiral_centers=Chem.FindMolChiralCenters(mol,includeUnassigned=True),
                optimized=bool(optimize),force_field=ff,optimization_status=status,
                limitation='Topology/reference geometry only; not measured crystal coordinates or absolute-structure evidence')
    output.parent.mkdir(parents=True,exist_ok=True); report.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation protects earlier outputs, including a concurrent writer.
    with output.open('x',encoding='utf-8') as f: f.write(Chem.MolToMolBlock(mol))
    with report.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--optimize',action='store_true')
    p.add_argument('--seed',type=int,default=0); p.add_argument('--max-iters',type=int,default=1000)
    a=p.parse_args()
    if a.max_iters<=0 or not 0<=a.seed<=2147483647: p.error('Invalid iteration limit or random seed')
    try: result=prepare(a.input,a.output,a.report,a.optimize,a.seed,a.max_iters)
    except (ImportError,OSError,ValueError) as exc: p.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
