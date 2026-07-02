#!/bin/bash
#SBATCH --job-name={JOB_NAME}
#SBATCH --account={ACCOUNT}
#SBATCH --qos={QOS}
#SBATCH --partition={PARTITION}
#SBATCH --gres={GRES}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={CPUS}
#SBATCH --mem={MEM}
#SBATCH --time={TIME}
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user={EMAIL}
#SBATCH --output={REMOTE_DIR}/slurm-%j.out

set -euo pipefail
echo "[$(date)] Starting MegaDetector on $(hostname)"
nvidia-smi || true

module load conda
source activate {CONDA_ENV}

python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

python -m megadetector.detection.run_detector_batch \
    MDV5A \
    "{INPUT_DIR}" \
    "{OUTPUT_JSON}" \
    --recursive \
    --output_relative_filenames

echo "[$(date)] Done. JSON written to {OUTPUT_JSON}"
