# from eventbus.bus.printer import Printer


from eventbus import event_type, eventbus


def init(exclude=[event_type.PONG, event_type.LOG]):
    @eventbus.on("*")
    def printer(type, **event):
        if type not in exclude:
            print(f"PRINT {type:12}", event)
