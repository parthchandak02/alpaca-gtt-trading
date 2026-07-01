# Security Notes

## Credential handling

- Never commit `.env` or real API keys. Use `.env.example` as the template.
- Machine-specific configs (`cloudflared-config.yml`, `ecosystem.config.js`) are gitignored — copy from `*.example` files.

## Past incident (Alpaca API key in git history)

A live Alpaca API key was previously committed in `update_keys.sh` on the public `alpaca-gtt-trading` repo.

**If you have not already:**

1. Rotate/revoke the exposed key in the [Alpaca dashboard](https://app.alpaca.markets/).
2. Push the security cleanup commit that removes `update_keys.sh` and untracks machine-specific configs.
3. Purge the key from Git history (required — deleting the file alone is not enough):

```bash
# Install: brew install git-filter-repo
cd /path/to/alpaca-trader
git filter-repo --path update_keys.sh --invert-paths --force
git remote add origin git@github.com:parthchandak02/alpaca-gtt-trading.git
git push origin main --force
```

> Only run `--force` push after confirming no collaborators need the old history.
