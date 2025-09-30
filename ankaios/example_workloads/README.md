# Ankaios Workload

In order to enhance the SDV lab with additional custom applications managed by Eclipse Ankaios, a containerised application is required.

This folder can be used as a starting point to create a workload and provides the following:

- Python workload
- Rust workload (shall be used if your workload must communicate with the existing uProtocol communication sdv lab infrastructure)

## Ankaios Control Interface

A workload managed by Ankaios can communicate via the [Ankaios Control Interface](https://eclipse-ankaios.github.io/ankaios/0.6/reference/control-interface/) with Ankaios itself. This is useful when your custom workload needs information about the state of other workloads or to request Ankaios to start or stop another workload dynamically.

For easy integration of the [Control Interface](https://eclipse-ankaios.github.io/ankaios/0.6/reference/control-interface/) in your app, there are two Ankaios SDKs ([ank-sdk-python](https://github.com/eclipse-ankaios/ank-sdk-python/tree/v0.6.0) and [ank-sdk-rust](https://github.com/eclipse-ankaios/ank-sdk-rust/tree/v0.6.0)) available.

The example workload for Python uses the `ank-sdk-python` and the example workload for Rust uses the `ank-sdk-rust`.

Both example workloads behave the same and demonstrate an dynamic workload start by:

- requesting Ankaios to create a workload named `dynamic_workload` dynamically
- using the workload states to wait until the newly added workload is in the state `Succeeded(Ok)`
- retrieving the current workload states of Ankaios

The [ank-sdk-python examples](https://github.com/eclipse-ankaios/ank-sdk-rust/tree/v0.6.0/examples) and [ank-sdk-rust examples](https://github.com/eclipse-ankaios/ank-sdk-rust/tree/v0.6.0/examples) provide lots of other examples of what you can do with the Control Interface.

Using the Control Interface is optional and you can remove the code from the example workloads and the `controlInterfaceAccess` configuration in their [manifest.yaml](manifest.yaml) if you do not need it in your specific use case.

## How to use

Please have a look into the dedicated example workload folder's README.md for detailed instructions.