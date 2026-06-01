import { SignJWT } from "jose";
import { ThreadFSServerError } from "./errors";

export type CreateThreadFSTokenInput = {
  /**
   * Shared secret configured in the ThreadFS community auth provider.
   * This must only exist on the host website backend.
   */
  secret: string;

  /**
   * Issuer registered in ThreadFS.
   * Example: "website123", "demo-site", "my-blog"
   */
  issuer: string;

  /**
   * Stable user id from the host website.
   * Example: Website123 user id.
   */
  subject: string;

  /**
   * Display name shown in ThreadFS comments.
   */
  username: string;

  /**
   * Optional user avatar URL shown in ThreadFS comments.
   */
  avatarUrl?: string | null;

  /**
   * JWT audience. Usually leave as "threadfs".
   */
  audience?: string;

  /**
   * Token lifetime in seconds.
   * Default: 15 minutes.
   */
  expiresInSeconds?: number;

  /**
   * Optional extra claims.
   * Keep this small and non-sensitive.
   */
  extraClaims?: Record<string, unknown>;
};

export type ThreadFSTokenClaims = {
  typ: "threadfs_external_user";
  username: string;
  avatar_url: string | null;
} & Record<string, unknown>;

const DEFAULT_AUDIENCE = "threadfs";
const DEFAULT_EXPIRES_IN_SECONDS = 15 * 60;

function assertNonEmptyString(value: string, fieldName: string): void {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ThreadFSServerError(`${fieldName} must be a non-empty string`);
  }
}

function assertSafeExpiresInSeconds(value: number): void {
  if (!Number.isFinite(value) || value <= 0) {
    throw new ThreadFSServerError("expiresInSeconds must be a positive number");
  }

  if (value > 24 * 60 * 60) {
    throw new ThreadFSServerError(
      "expiresInSeconds should not exceed 24 hours",
    );
  }
}

export async function createThreadFSToken({
  secret,
  issuer,
  subject,
  username,
  avatarUrl = null,
  audience = DEFAULT_AUDIENCE,
  expiresInSeconds = DEFAULT_EXPIRES_IN_SECONDS,
  extraClaims = {},
}: CreateThreadFSTokenInput): Promise<string> {
  assertNonEmptyString(secret, "secret");
  assertNonEmptyString(issuer, "issuer");
  assertNonEmptyString(subject, "subject");
  assertNonEmptyString(username, "username");
  assertNonEmptyString(audience, "audience");
  assertSafeExpiresInSeconds(expiresInSeconds);

  const now = Math.floor(Date.now() / 1000);
  const secretKey = new TextEncoder().encode(secret);

  const claims: ThreadFSTokenClaims = {
    ...extraClaims,
    typ: "threadfs_external_user",
    username,
    avatar_url: avatarUrl,
  };

  return new SignJWT(claims)
    .setProtectedHeader({
      alg: "HS256",
      typ: "JWT",
    })
    .setSubject(subject)
    .setIssuer(issuer)
    .setAudience(audience)
    .setIssuedAt(now)
    .setExpirationTime(now + expiresInSeconds)
    .sign(secretKey);
}
