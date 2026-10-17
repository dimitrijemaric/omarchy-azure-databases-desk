# Contributing

Open an issue describing the problem or proposed change before a large contribution. Keep Azure subscription IDs, account names, costs, credentials and screenshots of real resources out of public reports. Use fictional demo data for examples and follow [SECURITY.md](SECURITY.md) for vulnerabilities.

## Development

The runtime uses QML, Bash and the Python standard library. No Python package installation is required. Run from the repository root:

```bash
python3 -B scripts/check_release.py
python3 -B -m unittest discover -s tests
```

On an Omarchy desktop with Quickshell and the shell sources available:

```bash
omarchy plugin validate .
python3 -B scripts/qml_check.py
python3 -B scripts/simulate.py
```

All automated tests use local fixtures and temporary state. QML checks render real components offscreen. Simulation makes no Azure requests. Do not add live Azure calls, credentials or persistent user data to tests. GitHub CI runs portable release checks, shell syntax checks and the Python suite; native QML validation is a separate desktop check.

## Pull requests and releases

Describe the user-visible change and relevant verification. Preserve the plugin ID `azure-databases-desk`, keep entry points at safe repository-relative paths, and do not add install hooks, automatic package installation or resource-changing Azure operations. Document new commands, network access and storage in the README and security policy.

Update the manifest version and changelog for a release, validate the repository, and publish a GitHub tag/release matching the manifest. Marketplace review is tied to an exact commit; do not silently change a submitted snapshot. Use the marketplace's documented update/verification workflow for later listed releases.

Contributions are provided under this repository's [MIT license](LICENSE). Dependencies and third-party assets retain their own licenses.
