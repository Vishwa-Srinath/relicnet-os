// Run Next.js dev server inline to avoid Node 22 child-process exit bug
process.env.NEXT_TELEMETRY_DISABLED = '1';

const path = require('path');
const dir = __dirname;

async function main() {
  const { startServer } = require(path.join(dir, 'node_modules/next/dist/server/lib/start-server'));

  await startServer({
    dir,
    isDev: true,
    hostname: 'localhost',
    port: 3000,
    allowRetry: false,
    keepAliveTimeout: 5000,
  });

  console.log('> Ready on http://localhost:3000');

  // Keep process alive
  await new Promise(() => {});
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
