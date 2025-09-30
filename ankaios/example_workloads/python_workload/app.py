from ankaios_sdk import Workload, Ankaios, WorkloadStateEnum, AnkaiosException
import sys, signal

# Create a new Ankaios object.
# The connection to the control interface is automatically done at this step.
# The Ankaios class supports context manager syntax:
with Ankaios() as ankaios:

    def signal_handler(sig, frame):
        global ankaios
        del ankaios
        sys.exit(0)

    # Add a SIGTERM handler to allow a clean shutdown
    signal.signal(signal.SIGTERM, signal_handler)

    # Create a new workload
    workload = (
        Workload.builder()
        .workload_name("dynamic_workload")
        .agent_name("agent_A")
        .runtime("podman")
        .restart_policy("NEVER")
        .runtime_config(
            'image: docker.io/library/alpine\ncommandArgs: ["echo", "Hello from a dynamically started workload!"]\n'
        )
        .build()
    )

    try:
        # Run the workload
        update_response = ankaios.apply_workload(workload)

        # Get the WorkloadInstanceName to check later if the workload is running
        workload_instance_name = update_response.added_workloads[0]

        # Request the execution state based on the workload instance name
        ret = ankaios.get_execution_state_for_instance_name(
            workload_instance_name
        )
        if ret is not None:
            print(
                f"State: {ret.state}, substate: {ret.substate}, info: {ret.additional_info}"
            )

        # Wait until the workload reaches the running state
        try:
            ankaios.wait_for_workload_to_reach_state(
                workload_instance_name,
                state=WorkloadStateEnum.SUCCEEDED,
                timeout=5,
            )
        except TimeoutError:
            print("Workload didn't reach the required state in time.")
        else:
            print("Workload reached the RUNNING state.")

    # Catch the AnkaiosException in case something went wrong with apply_workload
    except AnkaiosException as e:
        print("Ankaios Exception occurred: ", e)

    # Request the state of the system, filtered with the workloadStates
    complete_state = ankaios.get_state(
        timeout=5, field_masks=["workloadStates"]
    )

    # Get the workload states present in the complete_state
    workload_states_dict = complete_state.get_workload_states().get_as_dict()

    # Print the states of the workloads:
    for agent_name in workload_states_dict:
        for workload_name in workload_states_dict[agent_name]:
            for workload_id in workload_states_dict[agent_name][workload_name]:
                print(
                    f"Workload {workload_name} on agent {agent_name} has the state "
                    + str(
                        workload_states_dict[agent_name][workload_name][
                            workload_id
                        ].state
                    )
                )
