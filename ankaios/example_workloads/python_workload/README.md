# Ankaios Python Workload

In order to enhance the SDV lab with additional custom applications managed by Eclipse Ankaios, a containerised application is required.

This folder can be used as a starting point to create a workload and provides the following:

| File             | Description                                                                                                                                    |
|------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| Dockerfile       | To create a container image from the app.                                                                                                      |
| app.py           | The file contains the code of your app written in Python. In this case, it uses the [ank-sdk-python](https://github.com/eclipse-ankaios/ank-sdk-python/tree/v0.6.0) (Ankaios Python SDK) to instruct Ankaios to create another workload dynamically. |
| manifest.yaml    | The [Ankaios manifest](https://eclipse-ankaios.github.io/ankaios/0.6/reference/startup-configuration/) to start the new workload with Ankaios. |
| requirements.txt | The Python packages required by the app.                                                                                                       |

## How to run

First you need to build your app with `Podman`:

```shell
sudo podman build -t localhost/example_python_workload:0.1 .
```

Afterwards, if not already running, start the Ankaios cluster:

```shell
sudo systemctl start ank-server ank-agent
```

Apply the new manifest containing your new app:

```shell
ank apply manifest.yaml
```

Get the states of the workloads:

```shell
ank get workloads
```

Delete the workloads:

```shell
ank delete workloads python_workload dynamic_workload
```

### Workload logs

For local development and debugging you might want to see the log output of your workloads.

Use the `ank-cli` to show the logs from one or multiple workloads:

```shell
ank logs -f python_workload dynamic_workload
```