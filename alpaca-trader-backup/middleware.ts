import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Check authentication status from cookie or header
  // For now, we'll handle auth client-side, but this can be extended
  // to check for auth tokens in cookies
  
  // Allow access to login page
  if (pathname === '/login') {
    return NextResponse.next();
  }
  
  // For protected routes, we'll handle redirects client-side
  // This middleware can be extended to check for auth tokens
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};

