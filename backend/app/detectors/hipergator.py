"""HiPerGator detector — runs MegaDetector on UFRC's HiPerGator cluster.

Workflow:
    1.  rsync project image dir -> /blue/ramccleery/<user>/lure_runs/<folder>/
    2.  Render sbatch from template, scp it to the cluster.
    3.  Submit with `sbatch`, capture job id.
    4.  Poll `squeue -j <id>` every N seconds; report state changes.
    5.  scp recognitionData.json back to the project's local folder.

Auth model:
    Relies on an ssh-config entry (default alias: `hpg`) that uses
    ControlMaster + ControlPersist. The user does Duo *once* per
    workday by running `ssh hpg` in a terminal, and from then on every
    ssh/scp/rsync call multiplexes over the same socket without prompting.

Why subprocess instead of paramiko:
    paramiko doesn't share OpenSSH ControlMaster sockets, so it would force
    a fresh Duo prompt on every call. Shelling out to `ssh hpg` inherits the
    multiplexed connection for free.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import sys
import time
from pathlib import Path
import asyncssh

from ..core.config import hipergator_settings as hpg
from .base import DetectionJob, ProgressCb


def _sbatch_template_path() -> Path:
    """Resolve the sbatch template for dev tree vs PyInstaller bundle.

    In the .app bundle, ``app/`` lives under ``Contents/Resources/app/`` and
    ``sbatch/`` is a sibling under ``Contents/Resources/sbatch/`` — *not*
    ``Contents/sbatch/`` (``parents[3]`` from this file wrongly points there).
    """
    here = Path(__file__).resolve()
    name = "run_pydetector_batch.template.sbatch"
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "sbatch" / name)
        # …/Resources/app/detectors/hipergator.py → parents[2] == Resources
        candidates.append(here.parents[2] / "sbatch" / name)
        candidates.append(here.parents[3] / "sbatch" / name)
    else:
        # …/backend/app/detectors/hipergator.py → parents[3] == repo root
        candidates.append(here.parents[3] / "sbatch" / name)
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not find run_pydetector_batch.template.sbatch. Tried:\n  "
        + "\n  ".join(str(c) for c in candidates)
    )


_SBATCH_TEMPLATE = _sbatch_template_path()

_TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT",
                    "NODE_FAIL", "PREEMPTED", "OUT_OF_MEMORY"}


def _sacct_state_tokens(sacct_out: str) -> list[str]:
    """Parse State column lines from ``sacct`` (handles header + multi-step rows)."""
    tokens: list[str] = []
    for raw in sacct_out.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper() in ("STATE", "JOBID"):
            continue
        # ``--format=State -P`` → one column; multi-column → state is last field.
        token = line.split("|")[-1].strip() if "|" in line else line
        if token:
            tokens.append(token)
    return tokens


def _job_completed_from_sacct(sacct_out: str) -> bool:
    return any(t.startswith("COMPLETED") for t in _sacct_state_tokens(sacct_out))


def _job_failed_token(sacct_out: str) -> str | None:
    for t in _sacct_state_tokens(sacct_out):
        if any(t.startswith(s) for s in _TERMINAL_STATES - {"COMPLETED"}):
            return t
    return None


class HiPerGatorSessionExpired(RuntimeError):
    """The ControlMaster socket is stale; user needs to re-auth in a terminal."""


_SESSION_EXPIRED_HINTS = (
    "Permission denied (keyboard-interactive)",
    "Permission denied (publickey,keyboard-interactive)",
    "no such identity",
)



async def _ssh(remote_cmd: str, check: bool = True) -> str:
    from ..core.ssh_pool import pool
    conn = await pool.get_connection()
    if not conn:
        raise HiPerGatorSessionExpired("No active SSH connection. Please Authenticate first.")
    
    try:
        result = await conn.run(remote_cmd, check=check)
        return result.stdout if isinstance(result.stdout, str) else ""
    except asyncssh.ProcessError as e:
        if check:
            raise RuntimeError(f"command {remote_cmd} failed (rc={e.exit_status}):\n"
                               f"  stderr: {e.stderr}\n  stdout: {e.stdout}")
        return ""
    except asyncssh.Error as e:
        raise HiPerGatorSessionExpired(f"SSH connection failed: {e}")


def _posix(path: Path) -> str:
    return path.as_posix()


def _render_sbatch(job: DetectionJob, remote_dir: str) -> str:
    template = _SBATCH_TEMPLATE.read_text()
    safe_folder = re.sub(r"[^A-Za-z0-9_.-]", "_", job.folder)
    return template.format(
        JOB_NAME=f"lure_{safe_folder}",
        ACCOUNT=hpg.account,
        QOS=hpg.qos,
        PARTITION=hpg.partition,
        GRES=hpg.gres,
        CPUS=hpg.cpus,
        MEM=getattr(job, "hpg_mem", hpg.mem),
        TIME=hpg.time,
        EMAIL=hpg.email or f"{hpg.ssh_alias}@example.local",
        REMOTE_DIR=remote_dir,
        CONDA_ENV=hpg.conda_env,
        INPUT_DIR=remote_dir,
        OUTPUT_JSON=f"{remote_dir}/recognitionData.json",
    )


_JOBID_RE = re.compile(r"Submitted batch job (\d+)")


class HiPerGatorDetector:
    name = "hipergator"

    def __init__(self, mem: str | None = None):
        self.mem = mem

    async def run(self, job: DetectionJob, on_progress: ProgressCb) -> Path:
        import os
        from ..core.ssh_pool import pool
        
        # Patch the job object with the memory override for the sbatch template
        job.hpg_mem = self.mem or hpg.mem

        conn = await pool.get_connection()
        if not conn:
            raise HiPerGatorSessionExpired("No active SSH connection. Please Authenticate first.")

        remote_dir = f"{hpg.remote_base.rstrip('/')}/{job.folder}"
        remote_json = f"{remote_dir}/recognitionData.json"
        remote_sbatch = f"{remote_dir}/run.sbatch"

        # --- 1. Upload ---
        await on_progress("uploading", 0.02,
                          f"Preparing {remote_dir} on HiPerGator", None)
        await _ssh(f"mkdir -p {remote_dir}")

        local_src = _posix(job.image_dir)

        await on_progress("uploading", 0.05,
                          f"Uploading images to {remote_dir}", None)
                          
        # High-performance streaming upload (compresses locally via tar and pipes over SSH)
        # This is ~100x faster than SFTP for tens of thousands of small files.
        await on_progress("uploading", 0.05, f"Compressing & uploading images to {remote_dir}", None)
        
        rel_files = []
        for root, dirs, files in os.walk(local_src):
            for file in files:
                if file.lower().endswith((".jpg", ".jpeg")):
                    rel = os.path.relpath(os.path.join(root, file), local_src)
                    rel_files.append(rel)
                    
        if rel_files:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write("\n".join(rel_files))
                tmp_file_list = f.name

            # 1. Start local tar process emitting to stdout
            env = os.environ.copy()
            env["COPYFILE_DISABLE"] = "1"
            proc_tar = await asyncio.create_subprocess_exec(
                "tar", "-cf", "-", "-T", tmp_file_list,
                cwd=local_src,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            # 2. Start remote tar extraction process
            remote_proc = await conn.create_process(f"cd '{remote_dir}' && tar -x >/dev/null 2>&1", encoding=None)
            
            # 3. Pipe stdout stream to remote stdin
            while True:
                chunk = await proc_tar.stdout.read(65536 * 4)
                if not chunk:
                    break
                remote_proc.stdin.write(chunk)
                await remote_proc.stdin.drain()
                
            remote_proc.stdin.write_eof()
            
            await proc_tar.wait()
            await remote_proc.wait()
            
            try:
                os.remove(tmp_file_list)
            except OSError:
                pass
            
            if remote_proc.exit_status != 0:
                err = await remote_proc.stderr.read()
                raise RuntimeError(f"Failed to extract uploaded files on HiPerGator: {err}")

        # --- 2. Write sbatch on cluster ---
        await on_progress("submitting", 0.4, "Writing sbatch script", None)
        sbatch_text = _render_sbatch(job, remote_dir)
        try:
            await conn.run(f"cat > {remote_sbatch}", input=sbatch_text)
        except asyncssh.ProcessError:
            raise RuntimeError(f"failed to write sbatch to {remote_sbatch}")

        # --- 3. Submit ---
        await on_progress("submitting", 0.45, "Submitting to SLURM", None)
        out = await _ssh(f"sbatch {remote_sbatch}")
        m = _JOBID_RE.search(out)
        if not m:
            raise RuntimeError(f"could not parse job id from sbatch output:\n{out}")
        jobid = m.group(1)

        await on_progress("queued", 0.5, f"Job {jobid} submitted; polling…", jobid)

        # --- 4. Poll ---
        last_state = ""
        poll_deadline = time.monotonic() + float(hpg.max_poll_hours) * 3600.0
        empty_sacct_streak = 0
        while True:
            if time.monotonic() > poll_deadline:
                raise RuntimeError(
                    f"Timed out waiting for SLURM job {jobid} after {hpg.max_poll_hours}h. "
                    "Check squeue/sacct on HiPerGator or increase HIPERGATOR_MAX_POLL_HOURS."
                )
            await asyncio.sleep(hpg.poll_sec)
            try:
                squeue_out = await _ssh(
                    f"squeue -j {jobid} -h -o '%T %r' 2>/dev/null", check=False
                )
            except RuntimeError:
                squeue_out = ""

            squeue_out = squeue_out.strip()
            if squeue_out:
                empty_sacct_streak = 0
                state = squeue_out.split()[0]
                pct = 0.55 if state == "PENDING" else 0.75
                if state != last_state:
                    await on_progress(
                        "queued" if state == "PENDING" else "running",
                        pct,
                        f"Job {jobid} {state}",
                        jobid,
                    )
                    last_state = state
                continue

            # Job is no longer in squeue; check sacct for the final state.
            sacct = await _ssh(
                f"sacct -j {jobid} --format=State -P -n -X 2>/dev/null",
                check=False,
            )
            if _job_completed_from_sacct(sacct):
                break
            fail_tok = _job_failed_token(sacct)
            if fail_tok is not None:
                log_tail = await _ssh(
                    f"tail -40 {remote_dir}/slurm-{jobid}.out 2>/dev/null",
                    check=False,
                )
                raise RuntimeError(
                    f"Job {jobid} ended in state {fail_tok}.\n"
                    f"--- tail of slurm log ---\n{log_tail}"
                )

            tokens = _sacct_state_tokens(sacct)
            if not tokens:
                empty_sacct_streak += 1
                # Accounting lag or sacct quirk: if results already exist, finish.
                if empty_sacct_streak * hpg.poll_sec >= float(hpg.sacct_stale_sec):
                    probe = await _ssh(
                        f"test -s {remote_json} && echo LURE_OK || echo LURE_NO",
                        check=False,
                    )
                    if "LURE_OK" in probe:
                        await on_progress(
                            "running",
                            0.92,
                            "Job left queue; detection output found on cluster — downloading",
                            jobid,
                        )
                        break
            else:
                empty_sacct_streak = 0
            # No squeue and sacct not decisive yet — wait again.

        # --- 5. Fetch JSON ---
        await on_progress("downloading", 0.95, "Downloading recognitionData.json", jobid)
        job.output_json.parent.mkdir(parents=True, exist_ok=True)
        sftp = await conn.start_sftp_client()
        await sftp.get(remote_json, _posix(job.output_json))
        sftp.exit()

        # --- 6. Optional cleanup ---
        if not hpg.keep_remote:
            await on_progress("cleanup", 0.98, "Cleaning up remote files", jobid)
            await _ssh(f"rm -rf {remote_dir}", check=False)

        await on_progress("done", 1.0, f"Job {jobid} complete", jobid)
        return job.output_json
