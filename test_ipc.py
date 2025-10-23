from bus.ipc import MessageBus
bus = MessageBus()
bus.publish("hi")
print("OK:", bus.poll())
