import { NextRequest, NextResponse } from 'next/server';

/**
 * Authentication endpoint that forces Traefik forward-auth middleware to trigger.
 * 
 * When an unauthenticated user hits this endpoint, Traefik intercepts the request
 * and redirects to Authentik for OAuth login. After successful authentication,
 * this endpoint redirects the user back to the chat page.
 */
export async function GET(request: NextRequest) {
  // Check if Authentik headers are present (set by Traefik middleware)
  const username = request.headers.get('x-authentik-username');
  
  if (!username) {
    // User is not authenticated - Traefik should have intercepted this,
    // but if we got here, return 401 to trigger authentication
    return new NextResponse('Unauthorized', { 
      status: 401,
      headers: {
        'WWW-Authenticate': 'Bearer realm="Authentik"'
      }
    });
  }
  
  // User is authenticated - redirect to chat
  // Use the host header to construct the correct URL
  const host = request.headers.get('host') || 'memex.shivelymedia.com';
  const protocol = request.headers.get('x-forwarded-proto') || 'https';
  const redirectUrl = `${protocol}://${host}/chat`;
  
  return NextResponse.redirect(redirectUrl);
}
