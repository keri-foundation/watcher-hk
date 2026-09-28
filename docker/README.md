# watcher-hk Docker image

The image is built and pushed by CI (`.github/workflows/build-push.yml`) on GitHub-hosted
`ubuntu-latest` runners, which produce `linux/amd64` images natively — matching the amd64
EKS node architecture used in production. No multi-platform buildx/QEMU setup is needed for
that path.

**Warning:** if building/pushing manually from an Apple Silicon (arm64) machine, you must pass
`--platform linux/amd64` explicitly, e.g.:

```
docker buildx build --platform linux/amd64 -f docker/Dockerfile -t weboftrust/watcher-hk:<tag> . --push
```

Without `--platform`, a native build on Apple Silicon defaults to `linux/arm64` and will fail
with `exec format error` when run on the amd64 EKS nodes. This is exactly how the image was
broken previously when built by hand from an Apple Silicon Docker Desktop host.

This assumes the EKS node group stays amd64-only. If arm64 (Graviton) nodes are ever added to
the cluster, this workflow will need multi-platform buildx + QEMU, matching how the earlier
manual verification build was done.
