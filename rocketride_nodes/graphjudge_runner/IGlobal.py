from rocketlib import IGlobalBase, OPEN_MODE


class IGlobal(IGlobalBase):
    def beginGlobal(self):
        if self.IEndpoint.endpoint.openMode == OPEN_MODE.CONFIG:
            return

    def endGlobal(self):
        return
