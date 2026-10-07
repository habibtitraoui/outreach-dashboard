import { createHash, timingSafeEqual } from 'node:crypto';
import { next } from '@vercel/functions';

export const config = {
  runtime: 'nodejs',
  matcher: ['/:path*'],
};

const challenge = 'Basic realm="EduFormation outreach dashboard", charset="UTF-8"';

function response(status: number, body: string, extra: Record<string, string> = {}) {
  return new Response(body, {
    status,
    headers: {
      'Cache-Control': 'private, no-store, max-age=0',
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      'X-Robots-Tag': 'noindex, nofollow, noarchive',
      ...extra,
    },
  });
}

function unauthorized() {
  return response(401, 'Authentication required.', {
    'WWW-Authenticate': challenge,
  });
}

function sameSecret(actual: string, expected: string) {
  const actualHash = createHash('sha256').update(actual, 'utf8').digest();
  const expectedHash = createHash('sha256').update(expected, 'utf8').digest();
  return actual.length === expected.length && timingSafeEqual(actualHash, expectedHash);
}

export default function middleware(request: Request) {
  const expected = process.env.DASHBOARD_PASSWORD;

  // Fail closed: a deployment without its secret can never serve the embedded
  // lead list, even if someone forgets to configure Vercel environment vars.
  if (!expected || expected.length < 24) {
    return response(
      503,
      'Dashboard access is not configured. Set DASHBOARD_PASSWORD to a secret of at least 24 characters.',
    );
  }

  const authorization = request.headers.get('authorization') || '';
  const encoded = authorization.match(/^Basic\s+(.+)$/i)?.[1];
  if (!encoded) return unauthorized();

  let credentials: string;
  try {
    credentials = Buffer.from(encoded, 'base64').toString('utf8');
  } catch {
    return unauthorized();
  }

  const separator = credentials.indexOf(':');
  const username = separator >= 0 ? credentials.slice(0, separator) : '';
  const password = separator >= 0 ? credentials.slice(separator + 1) : '';
  if (username !== 'outreach' || !sameSecret(password, expected)) return unauthorized();

  return next();
}
