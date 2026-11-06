async function run() {
  const response = await fetch("http://127.0.0.1:8000/stream?prompt=Explain+recursion", {
    method: "POST"
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    process.stdout.write(decoder.decode(value));
  }
}

run().catch(console.error);
