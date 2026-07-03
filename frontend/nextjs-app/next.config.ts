import type { NextConfig } from "next";

const securityHeaders = [
  // Prevent browsers from MIME-sniffing the content-type
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Block the page from being framed (clickjacking protection)
  { key: "X-Frame-Options", value: "DENY" },
  // Disable legacy XSS auditor (CSP is the modern replacement)
  { key: "X-XSS-Protection", value: "0" },
  // Referrer policy: send origin only on same-origin requests
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Permissions policy: disable features this dashboard doesn't use
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
