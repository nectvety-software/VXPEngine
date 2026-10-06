import sys, time, threading
from pathlib import Path

models_dir = Path("D:/Ollama/models")
gguf_files = list(models_dir.glob("*.gguf"))
if not gguf_files:
    print("No GGUF files found")
    sys.exit(1)

f = gguf_files[0]
print(f"Found: {f.name}")
print(f"Size: {f.stat().st_size / 1024 / 1024:.0f} MB")

result = []

def load():
    try:
        from llama_cpp import Llama
        t0 = time.time()
        llm = Llama(model_path=str(f), n_ctx=512, n_threads=2, n_gpu_layers=0, verbose=False)
        elapsed = time.time() - t0
        result.append(("ok", llm, elapsed))
    except Exception as e:
        result.append(("error", str(e)))

t = threading.Thread(target=load, daemon=True)
t.start()
t.join(timeout=60)

if not result:
    print("TIMEOUT - model loading stuck after 60s")
    sys.exit(1)

status, val, *rest = result[0]
if status == "ok":
    elapsed = rest[0]
    print(f"Loaded in {elapsed:.1f}s")
    t0 = time.time()
    out = val.create_chat_completion(
        messages=[{"role": "user", "content": "say hi"}],
        max_tokens=10, temperature=0
    )
    reply = out["choices"][0]["message"]["content"].strip()
    print(f"Inference: {reply}")
    print(f"Inference time: {time.time()-t0:.1f}s")
else:
    print(f"ERROR: {val}")
