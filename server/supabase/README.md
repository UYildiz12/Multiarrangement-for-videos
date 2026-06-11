# Supabase Deployment

This project keeps Supabase migrations in `server/supabase/migrations`.

For Supabase's GitHub integration, set:

- Working directory: `server`
- Deploy to production: enabled
- Required status check: enabled in GitHub branch protection

With that setup, pushes or merges to the production branch apply new migration files automatically.

This app still uses experimenter keys for owner authentication. Supabase Auth accounts are not required for the current key-only model.
