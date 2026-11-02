"""Exercise the packaged IF engine in real subprocesses, including its workers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--engine",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    session=dict(pid=os.getpid(),token=uuid.uuid4().hex,library_root=str(root/"library"))
    with (root/"engine.log").open("w") as log:
        restricted_path=str(Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32") if os.name=="nt" else "/usr/bin:/bin"
        worker=subprocess.Popen([str(args.engine.resolve()),"--stdio-server"],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=log,text=True,encoding="utf-8",env={**os.environ,"PATH":restricted_path})
        count=0
        def call(command,payload=None):
            nonlocal count
            count+=1
            worker.stdin.write(json.dumps(dict(request_id=count,command=command,payload=payload or {},session=session),ensure_ascii=False)+"\n")
            worker.stdin.flush();line=worker.stdout.readline()
            if not line:raise RuntimeError("Packaged engine exited; see engine.log")
            response=json.loads(line)
            assert response["request_id"]==count
            if not response["ok"]:raise ValueError(response["error"])
            return response["data"]
        def run(p,operation,options):
            j=call("if_start_job",dict(project=p,operation=operation,options=options))
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                state=call("if_job_status",dict(job_id=j["job_id"]))
                if state["status"] in ["completed","failed","cancelled"]:break
                time.sleep(.1)
            assert state["status"]=="completed",state
            return call("if_accept_job",dict(project=p,job_id=j["job_id"]))
        try:
            health=call("health");assert call("probe")["corrected_sum"]==80
            p=call("if_demo");assert p["synthetic"] and len(p["fields"])==6
            f=p["fields"][0];f["recipe"]["mode"]="nuclei";p["revision"]+=1
            p=run(p,"segment",dict(field_id=f["id"]));f=p["fields"][0]
            overlay=call("if_mask_preview",dict(field=f))
            assert overlay["label_count"]==9,overlay
            f["mask"]["confirmed"]=True;p["revision"]+=1
            p=run(p,"measure",dict(field_id=f["id"]));f=p["fields"][0]
            assert f["result"]["summary"][0]["object_count"]==9
            p=call("if_save",dict(project=p))
            old=Path(p["project_path"]);moved=root/("portable-"+uuid.uuid4().hex[:8]+".titanif")
            call("if_release",dict(path=str(old)));shutil.move(old,moved)
            p=call("if_open",dict(path=str(moved)))
            assert p["fields"][0]["mask"]["confirmed"]
            assert p["fields"][0]["result"]["summary"][0]["object_count"]==9
            figure=call("if_figure_preview",dict(project=p));assert figure["png"].startswith("data:image/png;base64,")
            figures=call("if_export_figure",dict(project=p,destination=str(root/("figure-"+uuid.uuid4().hex[:8]))))
            tables=call("if_export_results",dict(project=p,destination=str(root/("tables-"+uuid.uuid4().hex[:8]))))
            assert all(Path(path).is_file() for path in figures["files"]+tables["files"])
            record=dict(engine=str(args.engine.resolve()),health=health,synthetic=True,wb_probe=True,
                fields=6,nuclei=9,portable_reopen=True,worker_subprocess=True,
                figure_files=figures["files"],result_files=tables["files"],
                real_if_verified=False,windows_native_verified=False)
            (root/"verification.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(record,ensure_ascii=False))
        finally:
            worker.stdin.close()
            try:worker.wait(timeout=10)
            except subprocess.TimeoutExpired:worker.kill();worker.wait()


if __name__=="__main__":main()
