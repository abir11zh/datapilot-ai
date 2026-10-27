"""Execute this project's own EDA cells and retain real stdout, without adding Jupyter dependencies."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
path=ROOT/'notebooks/eda.ipynb'
nb=json.loads(path.read_text(encoding='utf-8'))
namespace={}
count=0
for cell in nb['cells']:
    if cell['cell_type']!='code':continue
    count+=1
    out=StringIO();start=time.perf_counter()
    with redirect_stdout(out):
        exec(compile(''.join(cell['source']),f'eda.ipynb:cell{count}','exec'),namespace)
    cell['execution_count']=count
    cell['outputs']=[{'name':'stdout','output_type':'stream','text':out.getvalue().splitlines(True)}] if out.getvalue() else []
    print(f'Cell {count}: {time.perf_counter()-start:.2f}s',flush=True)
nb['metadata']['datapilot_execution']='Executed all code cells using the existing Python environment and original workbook.'
path.write_text(json.dumps(nb,indent=2,ensure_ascii=False),encoding='utf-8')
print('All EDA notebook cells executed successfully.',flush=True)
