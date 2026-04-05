import { Auth0Client } from '@auth0/nextjs-auth0/server';

// ADR: authorizationParameters.audience at client level | Ensures every access
// token includes the API audience so API Gateway JWT authorizer accepts it
export const auth0 = new Auth0Client({
  authorizationParameters: {
    audience: process.env.AUTH0_AUDIENCE,
    scope: 'openid profile email offline_access',
  },
});
