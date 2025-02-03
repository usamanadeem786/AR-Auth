import base64
import hashlib
from datetime import UTC, datetime

from jwcrypto import jwk, jwt

from auth.models import Client, User
from auth.services.acr import ACR


def generate_id_token(
    signing_key: jwk.JWK,
    host: str,
    client: Client,
    authenticated_at: datetime,
    acr: ACR,
    user: User,
    lifetime_seconds: int,
    *,
    nonce: str | None = None,
    c_hash: str | None = None,
    access_token: str | None = None,
    encryption_key: jwk.JWK | None = None,
) -> str:
    """
    Generate an ID Token for an authenticated user.

    It's a signed JWT with claims following the OpenID specification.

    :param signing_key: The JWK to sign the JWT.
    :host: The issuer host.
    :client: The client used to authenticate the user.
    :authenticated_at: Date and time at which the user authenticated.
    :acr: ACR level.
    :user: The authenticated user.
    :lifetime_seconds: Lifetime of the JWT.
    :nonce: Optional nonce value associated with the authorization request.
    :c_hash: Optional c_hash value to add to the claims.
    :access_token: Optional access token associated to the ID Token.
    :encryption_key: Optional JWK to further encrypt the signed token.
    In this case, it becomes a Nested JWT, as defined in rfc7519.
    """
    iat = int(datetime.now(UTC).timestamp())
    exp = iat + lifetime_seconds

    claims = {
        **user.get_claims(),
        "iss": host,
        "aud": [client.client_id],
        "exp": exp,
        "iat": iat,
        "auth_time": int(authenticated_at.timestamp()),
        "acr": str(acr),
        "azp": client.client_id,
    }

    if nonce is not None:
        claims["nonce"] = nonce
    if c_hash is not None:
        claims["c_hash"] = c_hash
    if access_token is not None:
        claims["at_hash"] = get_validation_hash(access_token)

    signed_token = jwt.JWT(
        header={"alg": "RS256", "kid": signing_key["kid"]}, claims=claims
    )
    signed_token.make_signed_token(signing_key)

    if encryption_key is not None:
        encrypted_token = jwt.JWT(
            header={
                "alg": "RSA-OAEP-256",
                "enc": "A256CBC-HS512",
                "kid": encryption_key["kid"],
            },
            claims=signed_token.serialize(),
        )
        encrypted_token.make_encrypted_token(encryption_key)
        return encrypted_token.serialize()

    return signed_token.serialize()


def get_validation_hash(value: str) -> str:
    """
    Computes a hash value to be embedded in the ID Token, like at_hash and c_hash.

    Specification: https://openid.net/specs/openid-connect-core-1_0.html#toc
    """
    hasher = hashlib.sha256()
    hasher.update(value.encode("utf-8"))
    hash = hasher.digest()

    half_hash = hash[0 : int(len(hash) / 2)]
    # Remove the Base64 padding "==" at the end
    base64_hash = base64.urlsafe_b64encode(half_hash)[:-2]

    return base64_hash.decode("utf-8")
