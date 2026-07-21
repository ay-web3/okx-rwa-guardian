const cp = require('child_process');

async function test(endpoint, assetName, lat, lon) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Testing [${endpoint}]: ${assetName} (${lat}, ${lon})`);
  console.log('='.repeat(60));
  
  const url = `https://okx-rwa-guardian.onrender.com${endpoint}`;

  console.log('Fetching initial challenge...');
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_name: assetName, lat, lon })
  });
  
  console.log('Status 1:', r.status);
  const pr = r.headers.get('payment-required');
  if (!pr) {
    console.log('No payment-required header. Body:', await r.text());
    return;
  }
  
  console.log('Signing with onchainos payment pay...');
  const child = cp.spawnSync('onchainos', ['payment', 'pay', '--payload', pr], { encoding: 'utf8' });
  if (child.status !== 0) {
    console.error('onchainos failed:', child.stderr || child.stdout);
    return;
  }
  
  const sig = JSON.parse(child.stdout);
  console.log('Sending signed payment...');
  
  const r2 = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'PAYMENT-SIGNATURE': sig.data.authorization_header
    },
    body: JSON.stringify({ asset_name: assetName, lat, lon })
  });
  
  console.log('Status 2:', r2.status);
  const body = await r2.text();
  
  // Pretty print
  try {
    console.log(JSON.stringify(JSON.parse(body), null, 2));
  } catch {
    console.log(body);
  }
}

async function runTests() {
  // Consumer endpoint test
  await test('/api/v1/consumer/risk_report', 'Miami Condo (Consumer)', 25.79, -80.13);
  
  // Oracle endpoint test
  await test('/api/v1/oracle/risk_verdict', 'Puerto Madero (Oracle)', 14.1592, -92.9052);
}

runTests().catch(console.error);
