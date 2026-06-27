/** @type {import('next').NextConfig} */
module.exports = {
  output: "standalone",
  reactStrictMode: true,
  swcMinify: false,
  experimental: {
    forceSwcTransforms: false,
  },
};
