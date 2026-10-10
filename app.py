import os
import jwt
from functools import wraps
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# must be the SAME value the auth service signs with
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise SystemExit("Set JWT_SECRET first (same value as auth-service).")


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Missing token."), 401
        try:
            claims = jwt.decode(
                header[7:], JWT_SECRET, algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        except jwt.InvalidTokenError:       # bad signature, expired, malformed
            return jsonify(error="Invalid or expired token."), 401

        # a temporary 2FA token must never open the tracker
        if claims.get("purpose") != "access":
            return jsonify(error="Invalid or expired token."), 401

        g.user_id = int(claims["sub"])
        g.email = claims["email"]
        return f(*args, **kwargs)
    return wrapper


@app.route("/api/me")
@token_required
def me():
    return jsonify(user_id=g.user_id, email=g.email)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5002)