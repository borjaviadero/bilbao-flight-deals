# Contributing

Conventions used in this repository.

## Language

Everything in the repository is written in **English**: code, comments, docs, commit messages and pull requests.

## Workflow

1. Create a branch from `main`.
2. Commit small, focused changes.
3. Open a pull request using the template.
4. Review and merge. `main` always holds the reviewed, working state.

## Branch names

`<type>/<short-description>`, for example `feat/flights-watcher` or `docs/architecture`.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>: <summary in imperative mood>
```

| Type | Use for |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fixes |
| `docs` | Documentation only |
| `chore` | Repository setup, tooling, maintenance |
| `ci` | GitHub Actions workflows |
| `infra` | Terraform and Kubernetes changes |
| `refactor` | Code changes that don't change behaviour |
| `test` | Tests |

## Secrets

Never commit tokens, keys, `.env` files, `*.tfvars` or Terraform state. They are excluded in [`.gitignore`](.gitignore). Use `*.example` files to document required variables.
