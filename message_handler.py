import json
from message import GapiMicroServiceMessage

async def on_message(micro_service_msg, websocket, logger):
    try:
        #micro_service_msg is a wrapper that has json string and binary data
        
        request_json_str = micro_service_msg.json_data;
        logger.info(f"Inbound msg: {request_json_str}")

        # parse as object as you please
        request_json_obj = json.loads(request_json_str)

        response_bin_data = None

        # and here sometimes there is binary data
        if len(micro_service_msg.bin_data) > 0:
            logger.info("Request has binary payload")
            # update response_bin_data if you need to send binary


        # take action here including the handling of bin_data as needed
        # formulate custom response as object
        custom_response_obj = {
            "field1": 10,
            "field2": "bacon"
        }

        # pack as string version
        request_json_obj["message"] = json.dumps(custom_response_obj);
        
        # essentially sending back the request object plus any custom "message" data and/or binary
        
        response_msg = GapiMicroServiceMessage(json.dumps(request_json_obj), response_bin_data)
        response_payload: bytearray = response_msg.encode()

        await websocket.send(response_payload)

        response_str = response_msg.json_data
        logger.info(f"Response sent: {response_str}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
