Got it ✅ Here’s a **clean README** you can drop into your project that explains how to build, run, and test your **Ankaios Python workload** using Docker.

---

# Ankaios Python Workload

This example shows how to containerize a Python application and run it as a workload managed by [Eclipse Ankaios](https://eclipse-ankaios.github.io/ankaios/).
It uses the [ank-sdk-python](https://github.com/eclipse-ankaios/ank-sdk-python/tree/v0.6.0) to interact with Ankaios dynamically.

---

## 📂 Project Contents

| File               | Description                                                                                                                   |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `Dockerfile`       | Multi-stage Dockerfile to build the Python app and package it with Ankaios.                                                   |
| `app.py`           | Python application using the Ankaios Python SDK.                                                                              |
| `manifest.yaml`    | The [Ankaios manifest](https://eclipse-ankaios.github.io/ankaios/0.6/reference/startup-configuration/) defining the workload. |
| `requirements.txt` | Python dependencies for the app.                                                                                              |

---

## 🚀 How to Build and Run

### 1. Build the image

From the folder containing the Dockerfile:

```bash
docker build -t my-ankaios-app .
```

### 2. Start a container with Ankaios running

```bash
docker run -it --rm my-ankaios-app \
  sh -c "ank-server & ank-agent & sleep 5 && bash"
```

This will:

* Start the **Ankaios server** and **agent** in the background.
* Drop you into a shell inside the container so you can run `ank` commands.

---

## 🧪 Test the Workload

Inside the container shell:

### Apply the manifest

```bash
ank apply /usr/src/app/manifest.yaml
```

### Check workloads

```bash
ank get workloads
```

Expected output (states may vary as workloads start up):

```
WORKLOAD NAME     AGENT     RUNTIME   EXECUTION STATE     ADDITIONAL INFO
python_workload   agent_A   podman    Pending(Starting)   Triggered at runtime.
```

### Delete workloads

```bash
ank delete workloads python_workload
```

### Re-apply workloads

```bash
ank apply /usr/src/app/manifest.yaml
```

---

## 🔄 Development Tips

* If you rebuild your app and want Ankaios to pick it up, bump the image tag and update it in `manifest.yaml`.
  Example:

  ```bash
  docker build -t my-ankaios-app:0.2 .
  ```

  Update manifest:

  ```yaml
  image: my-ankaios-app:0.2
  ```

  Re-apply:

  ```bash
  ank apply /usr/src/app/manifest.yaml
  ```

* To see logs or debug interactively:

  ```bash
  docker run -it --rm my-ankaios-app bash
  ```

---

👉 Do you want me to also add a **troubleshooting section** in the README (e.g., “connection refused” if Podman inside Ankaios tries to pull from `localhost`)?
