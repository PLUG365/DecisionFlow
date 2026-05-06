const fs = require('fs');
const path = require('path');
const os = require('os');

const pacCliBase = path.join(os.homedir(), 'AppData', 'Local', 'Microsoft', 'PowerAppsCLI');
const dirs = fs.readdirSync(pacCliBase).filter(d => d.startsWith('Microsoft.PowerApps.CLI.')).sort().reverse();
if (!dirs.length) { console.log('PAC CLI not found'); process.exit(1); }

const binJs = path.join(pacCliBase, dirs[0], 'tools', 'Bin.js');
console.log('Target:', binJs);

let c = fs.readFileSync(binJs, 'utf8');
const oldPat = '/[^a-zA-Z0-9_$]/g,"_"';
const newPat = '/[^a-zA-Z0-9_$\\u00C0-\\u024F\\u0370-\\u03FF\\u0400-\\u04FF\\u3000-\\u9FFF\\uAC00-\\uD7AF\\uF900-\\uFAFF]/g,"_"';

if (c.includes(newPat)) {
  console.log('Already patched');
} else if (c.includes(oldPat)) {
  c = c.replaceAll(oldPat, newPat);
  fs.writeFileSync(binJs, c, 'utf8');
  console.log('Patched successfully');
} else {
  console.log('Pattern not found - Bin.js may have changed');
}
