# 📋 Pipeline: Job Application Tracker

A job application tracker with a drag-and-drop status board. It has **no login code of its own**. Users sign in through my separate [auth-service](https://github.com/Kevin03-cyber/Auth-service) (password and 2FA), and the tracker verifies the **JWT** that service issues.

## 📸 Screenshots

| Login | 2FA code step |
|---|---|
| <img width="1908" height="977" alt="image" src="https://github.com/user-attachments/assets/8504b0d2-95c9-4ee9-9cff-1bc5a110cfc6" />
 | <img width="1908" height="977" alt="image" src="https://github.com/user-attachments/assets/6b6101a4-d766-453b-9b09-2351f97eca5c" />
 |

| Board (light) | Board (dark) |
|---|---|
| <img width="1913" height="981" alt="image" src="https://github.com/user-attachments/assets/46878de2-8908-4c53-933b-9266d7ffacc0" />
 | <img width="1898" height="972" alt="image" src="https://github.com/user-attachments/assets/7635c34f-b2e4-4f00-b0ba-f2de259f1717" />
 |

## ✨ Features

- Four-stage board: **Applied, Interview, Offer, Rejected**
- Drag and drop between stages (or use the arrow buttons)
- Add and delete applications, with notes
- Live stats: stage donut chart, interview rate and applications per week
- Search by company, role or notes
- Light and dark theme, remembered between visits
- Login with two-factor authentication through the auth service
- Every user sees **only their own** applications

## 🔌 How it fits together

```
 Browser ──login + 2FA──► auth-service (port 5001) ──► signed JWT
    │
    └──JWT in every request──► job-tracker (port 5002)
                                  │
                                  ├─ checks signature, expiry and purpose
                                  └─ reads user id from the token, queries only that user's rows
```

The tracker never sees a password. It trusts a token only if the signature matches the shared `JWT_SECRET`.

## 🌐 API

All routes need `Authorization: Bearer <token>`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/me` | Who the token belongs to |
| GET | `/api/applications` | List my applications (`?status=Interview` to filter) |
| POST | `/api/applications` | Create an application |
| PATCH | `/api/applications/<id>` | Update status, company, role, date or notes |
| DELETE | `/api/applications/<id>` | Delete an application |

## 🛠️ Tech stack

Python · Flask · SQLite · PyJWT · vanilla JavaScript (no framework)

## 🚀 Run locally

You need **both** servers running, with the **same** secret.

1. Generate a secret (any long random string):
```
   python -c "import secrets; print(secrets.token_hex(32))"
```
2. Start the auth service:
```
   git clone https://github.com/Kevin03-cyber/Auth-service.git
   cd Auth-service
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   $env:JWT_SECRET="your-secret"
   python app.py
```
3. Start the tracker in a second terminal:
```
   git clone https://github.com/Kevin03-cyber/job-tracker.git
   cd job-tracker
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   $env:JWT_SECRET="your-secret"
   python app.py
```
4. Open **http://127.0.0.1:5002/**, create an account, and log in.

Use `127.0.0.1`, not `localhost`. The auth service only allows requests from that exact address.

## 🛡️ Security design

- The tracker stores no passwords. It only verifies tokens from the auth service
- Tokens are checked for signature, expiry and **purpose**, so a half-finished 2FA login token is rejected
- The owner of every record comes from the verified token, never from the request body
- Ownership is enforced in the SQL (`WHERE id = ? AND user_id = ?`), so one user can't read, edit or delete another's data
- Other users' records return 404 instead of 403, so their existence isn't revealed
- All queries are parameterized, and update fields come from a fixed allow-list
- User text is rendered with `textContent`, so it can't inject HTML or scripts
- Cross-origin access on the auth service is limited to this app's address
- Debug mode is off by default

## ⚠️ Known limitations

- Access tokens last 30 minutes and there are no refresh tokens, so you log in again after that
- The token is kept in `sessionStorage`, which scripts on the page can read, so any XSS flaw would expose it
- HS256 uses one shared secret between the two services (RS256 would let apps verify with a public key only)
- Tokens can't be revoked before they expire
- The interface moves and deletes applications, but editing company, role or notes is only available through the API
- No pagination, and no automated tests yet
- Needs HTTPS and a production server (not Flask's dev server) before real deployment

## 🔮 Next steps

- Edit form and interview dates with reminders
- Automated tests for the ownership rules
- RS256 tokens and refresh tokens
- Reuse the same auth service in a monitoring platform

## 👤 Author

Kevin · [GitHub](https://github.com/Kevin03-cyber)
