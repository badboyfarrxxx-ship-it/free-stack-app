import httpx

# Set timeout=None to allow continuous streaming without 5-second cutoffs
with httpx.stream(
    "POST", 
    "http://127.0.0.1:8000/stream?prompt=Explain+recursion", 
    timeout=None
) as r:
    for chunk in r.iter_text():
        print(chunk, end="", flush=True)
