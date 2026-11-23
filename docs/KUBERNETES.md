# Kubernetes (local practice only)

## Honesty rule — read first
This is **local practice with a kind cluster, not production Kubernetes, and not AWS/EKS.**
Nothing here has been run in production, and it does not support the claim "I have run
Kubernetes in production." The manifests in `infra/k8s/` were, at the time they were added,
**validated with kubeconform only — no cluster was started** (the authoring machine had no
Docker). Production for this project is still the Railway deploy.

## What is here
`infra/k8s/`: `namespace.yaml`, `configmap.yaml`, `deployment.yaml`, `service.yaml`,
`kustomization.yaml`, `kind-config.yaml`, and `secret.example.yaml` (template with
placeholders; never commit real values). The Deployment runs the **existing repo-root
`Dockerfile`** image — there is no second image.

Probes (added in `agent/web_server.py`, tests in `agent/test_health_endpoints.py`):
- `GET /healthz` — liveness; no I/O, never touches a dependency.
- `GET /readyz` — readiness; no network I/O. Reports `ledger: configured|not_configured`
  (whether `EVENT_LEDGER_DATABASE_URL` is set). The ledger is optional and spool-backed, so it
  deliberately does **not** affect readiness (`ledger_affects_readiness: false`).
  The Deployment also has a `startupProbe` because the image is large.

## Validate manifests (no Docker needed)
```
kubeconform -strict -summary -ignore-filename-pattern 'kustomization.yaml|kind-config.yaml' infra/k8s
```
CI runs this (job `k8s-manifests`).

## Bring up on kind (needs Docker + kind + kubectl) — UNTESTED by the author
```
kind create cluster --config infra/k8s/kind-config.yaml \
 && docker build -t asd-platform:local . \
 && kind load docker-image asd-platform:local --name asd \
 && kubectl apply -k infra/k8s \
 && kubectl -n asd rollout status deploy/asd-platform --timeout=300s \
 && kubectl -n asd port-forward svc/asd-platform 8420:80
# then: curl localhost:8420/healthz  and  /readyz
```
Optional secrets: `kubectl -n asd create secret generic asd-platform-secrets --from-literal=...`
(see `secret.example.yaml`). Tear down: `kind delete cluster --name asd`.
If you run this, record what you actually saw; do not paste imagined output.

## What would change on EKS (not done)
- Image pushed to a registry (ECR) instead of `kind load`; `imagePullPolicy` and tag pinned.
- Service becomes an Ingress/ALB (AWS Load Balancer Controller) with TLS, or `type: LoadBalancer`.
- Secrets from AWS Secrets Manager / External Secrets or sealed secrets, not `kubectl create`.
- Probes tuned to real startup times; PodDisruptionBudget, multiple replicas, resource limits
  from measurement, NetworkPolicies, IAM roles for service accounts.
- Persistent state: the platform writes run history/spool to local disk; that needs a
  PersistentVolume or a redesign before more than one replica is safe.
- The image also bundles git, a JDK and the Railway CLI for the Workbench deploy path;
  running that inside a cluster is a separate security decision.
