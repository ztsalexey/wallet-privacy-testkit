"""The small part of the lightwalletd protocol needed by the fault relay."""

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

SERVICE = "cash.z.wallet.sdk.rpc.CompactTxStreamer"
SEND_TRANSACTION = f"/{SERVICE}/SendTransaction"


def _message_classes():
    schema = descriptor_pb2.FileDescriptorProto(
        name="wallet_privacy_testkit.proto",
        package="cash.z.wallet.sdk.rpc",
        syntax="proto3",
    )
    definitions = (
        ("RawTransaction", (("data", 1, 12), ("height", 2, 4))),
        ("SendResponse", (("errorCode", 1, 5), ("errorMessage", 2, 9))),
    )
    for name, fields in definitions:
        message = schema.message_type.add(name=name)
        for field_name, number, field_type in fields:
            message.field.add(name=field_name, number=number, type=field_type, label=1)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(schema)
    return tuple(
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName(f"cash.z.wallet.sdk.rpc.{name}")
        )
        for name in ("RawTransaction", "SendResponse")
    )


RawTransaction, SendResponse = _message_classes()
