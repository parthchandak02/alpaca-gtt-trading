# Security Notes

## Credential handling

- Never commit `.env` or real API keys. Use `.env.example` as the template.
- Machine-specific configs (`cloudflared-config.yml`, `ecosystem.config.js`) are gitignored — copy from `*.example` files.

## Past incident (Alpaca API key in git history)

A live Alpaca API key was previously committed in `update_keys.sh` on the public `alpaca-gtt-trading` repo.

**Remediation status (2026-07-01):**

- [x] Alpaca API key rotated by owner
- [x] `update_keys.sh` removed from repo and git history (`git filter-repo`)
- [x] Purged history force-pushed to `parthchandak02/alpaca-gtt-trading`
- [x] GitHub code search returns 0 matches for the old key string

If you clone on a new machine, copy `cloudflared-config.example.yml` → `cloudflared-config.yml` and `ecosystem.config.example.js` → `ecosystem.config.js`.
