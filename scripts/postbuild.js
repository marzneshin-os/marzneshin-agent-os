import fs from 'node:fs';
import path from 'node:path';

const copyFiles = [
  'iii-config.yaml',
  'iii-config.docker.yaml',
  'docker-compose.yml',
  '.env.example',
];

for (const file of copyFiles) {
  if (fs.existsSync(file)) {
    fs.copyFileSync(file, path.join('dist', file));
  }
}

fs.mkdirSync(path.join('dist', 'viewer'), { recursive: true });
if (fs.existsSync(path.join('src', 'viewer', 'index.html'))) {
  fs.copyFileSync(path.join('src', 'viewer', 'index.html'), path.join('dist', 'viewer', 'index.html'));
}
if (fs.existsSync(path.join('src', 'viewer', 'favicon.svg'))) {
  fs.copyFileSync(path.join('src', 'viewer', 'favicon.svg'), path.join('dist', 'viewer', 'favicon.svg'));
}

console.log('Postbuild assets copied successfully.');
