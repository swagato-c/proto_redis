from collections import deque
from .proto_redis import ProtoRedis
import asyncio
import operator
import hiredis
import sys
import functools

meta = {b"get": "get", b"ping": "ping"}


def serialize_to_wire(value):
    if isinstance(value, str):
        return ('+%s' % value).encode() + b'\r\n'
    elif isinstance(value, bool) and value:
        return b"+OK\r\n"
    elif isinstance(value, int):
        return (':%s' % value).encode() + b'\r\n'
    elif isinstance(value, bytes):
        return (b'$' + str(len(value)).encode() +
                b'\r\n' + value + b'\r\n')
    elif isinstance(value, Exception):
        return ('-%s' % str(value)).encode() + b'\r\n'
    elif value is None:
        return b'$-1\r\n'
    elif isinstance(value, list):
        base = b'*' + str(len(value)).encode() + b'\r\n'
        for item in value:
            base += serialize_to_wire(item)
        return base


class ProtoRedisProtocol(asyncio.Protocol):
    def __init__(self, db: ProtoRedis):
        self._db = db
        self.response = deque()
        self.parser = hiredis.Reader()

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport

    def data_received(self, data: bytes):
        self.parser.feed(data)

        while True:
            request = self.parser.gets()
            if not request:
                break
            print(request[0])

            try:
                resp = getattr(self._db, meta.get(
                    request[0], 'invalid'))(*request[1:])
            except Exception as e:
                resp = e
            self.response.append(serialize_to_wire(resp))

        self.transport.writelines(self.response)
        self.response.clear()


def main(hostname='127.0.0.1', port=6970) -> int:
    loop = asyncio.get_event_loop()

    bound_protocol = functools.partial(ProtoRedisProtocol, ProtoRedis())
    coro = loop.create_server(bound_protocol, hostname, port)
    server = loop.run_until_complete(coro)
    print("Listening on port {}".format(port))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("User requested shutdown.")
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
        print("Redis is now ready to exit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
