#!/bin/bash
#SBATCH --job-name=ollama_qa
#SBATCH --output=ollama_output.log
#SBATCH --error=ollama_error.log
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00

CONTAINER="/ceph/container/ollama_latest.sif"

export OLLAMA_MODELS="$HOME/.ollama/models"
mkdir -p $OLLAMA_MODELS

# Export user info so the container knows who you are
getent passwd $(id -u) > /tmp/mypasswd_$SLURM_JOB_ID
getent group $(id -g) > /tmp/mygroup_$SLURM_JOB_ID

# 1. Start the Ollama server
singularity exec --nv \
    -B /tmp/mypasswd_$SLURM_JOB_ID:/etc/passwd \
    -B /tmp/mygroup_$SLURM_JOB_ID:/etc/group \
    --env OLLAMA_MODELS=$OLLAMA_MODELS \
    $CONTAINER ollama serve &
OLLAMA_PID=$!

# 2. Wait for the server to be ready (up to 2 minutes)
echo "Waiting for Ollama server to start..."
WAIT=0
until curl -s http://localhost:11434 > /dev/null; do
    sleep 2
    WAIT=$((WAIT+2))
    if [ $WAIT -ge 120 ]; then
        echo "ERROR: Ollama server failed to start after 120s"
        kill $OLLAMA_PID
        exit 1
    fi
done
echo "Server is up!"

# 3. Download the AI model (only needed the first time)
singularity exec --nv \
    -B /tmp/mypasswd_$SLURM_JOB_ID:/etc/passwd \
    -B /tmp/mygroup_$SLURM_JOB_ID:/etc/group \
    --env OLLAMA_MODELS=$OLLAMA_MODELS \
    $CONTAINER ollama pull qwen2.5:7b

# 4. Run your Python questions
singularity exec \
    -B /tmp/mypasswd_$SLURM_JOB_ID:/etc/passwd \
    -B /tmp/mygroup_$SLURM_JOB_ID:/etc/group \
    /ceph/container/python/python_3.13.sif python3 /ceph/project/agentic-healthcare/code/agent1.py

# 5. Shut down the server
echo "Shutting down Ollama..."
kill $OLLAMA_PID
