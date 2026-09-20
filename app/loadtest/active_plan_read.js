import http from 'k6/http';
import { check, sleep } from 'k6';

// Real load-test baseline for GET /customers/{id}/plan -- was flagged
// NOT_STARTED/P1 in docs/FLAGSHIP_MARKET_COVERAGE.md ("no baseline
// established yet"). Chosen specifically because it exercises the
// cache-aside layer (cache/ContractPlanCacheService.java): with Redis
// reachable, this measures a real mixed hit/miss workload; with Redis
// unreachable (documented per-run in the results, see loadtest/README.md),
// every request takes the real, already-proven fallback-to-database path
// -- still a genuine, useful baseline, just for the uncached case.
//
// setup() runs ONCE before the load phase: gets a real demo JWT (one
// call -- stays well under RateLimiterService's 20/min limit on
// /auth/demo-token) and creates one real customer with one real active
// plan, so every VU reads the SAME real row -- a realistic "popular
// customer" read pattern, not N different rows that would never let a
// cache layer show a hit at all.
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export const options = {
  scenarios: {
    steady_read_load: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'], // real, meaningful ceiling for a single-row read; not tuned to whatever the first run happened to produce
    http_req_failed: ['rate<0.01'],
  },
};

export function setup() {
  const tokenRes = http.post(`${BASE_URL}/auth/demo-token`);
  if (tokenRes.status !== 200) {
    throw new Error(`Could not obtain demo token: ${tokenRes.status} ${tokenRes.body}`);
  }
  const token = tokenRes.json('access_token');
  const authHeaders = { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };

  const customerRes = http.post(`${BASE_URL}/customers`,
    JSON.stringify({ name: 'k6 Load Test Customer', email: `k6-loadtest-${Date.now()}@example.com` }),
    authHeaders);
  if (customerRes.status !== 201) {
    throw new Error(`Could not create test customer: ${customerRes.status} ${customerRes.body}`);
  }
  const customerId = customerRes.json('id');

  const enrollRes = http.post(`${BASE_URL}/customers/${customerId}/plan`,
    JSON.stringify({ planName: 'k6 Baseline Plan', ratePerKwh: 0.15, effectiveStartDate: new Date().toISOString().slice(0, 10) }),
    authHeaders);
  if (enrollRes.status !== 201) {
    throw new Error(`Could not enroll test plan: ${enrollRes.status} ${enrollRes.body}`);
  }

  return { token, customerId };
}

export default function (data) {
  const res = http.get(`${BASE_URL}/customers/${data.customerId}/plan`, {
    headers: { Authorization: `Bearer ${data.token}` },
  });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'returned the real plan name': (r) => r.json('planName') === 'k6 Baseline Plan',
  });
  sleep(0.1);
}
