let chunks = [];
process.stdin.on('data', chunk => { chunks.push(chunk); });
process.stdin.on('end', () => {
  try {
    let raw = Buffer.concat(chunks).toString('utf8').replace(/^\uFEFF/, '').trim();
    if (!raw) {
      process.stdout.write(JSON.stringify({}));
      return;
    }
    const payload = JSON.parse(raw);
    const cmd = payload?.toolCall?.args?.CommandLine || '';
    const isAutoApproved = /^\s*(python3|python|git|pytest)\b/i.test(cmd);
    if (isAutoApproved) {
      process.stdout.write(JSON.stringify({
        decision: 'allow',
        reason: 'Auto-approved command by policy (python3, git, pytest)'
      }));
    } else {
      process.stdout.write(JSON.stringify({}));
    }
  } catch (err) {
    process.stdout.write(JSON.stringify({}));
  }
});