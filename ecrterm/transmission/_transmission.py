"""
Transmission Basics.
@author g4b
"""
import logging

from ecrterm.exceptions import TransmissionException, TransportLayerException
from ecrterm.packets.base_packets import PacketReceived, Packet
from ecrterm.transmission.signals import TIMEOUT_T4_DEFAULT, TRANSMIT_OK

logger = logging.getLogger('ecrterm.transmission')

class Transmission(object):
    """
    A Transmission Object represents an open connection between ECR and
    PT. It regulates the flow of packets, and uses a Transport to send
    its data. The default Transport to use is the serial transport.
    """
    actual_timeout = TIMEOUT_T4_DEFAULT
    last = None

    def __init__(self, transport):
        self.transport = transport
        self.is_master = True
        self.is_waiting = False
        self.last = None  # saves last sent master
        self.log_list = []
        self.history = []
        self.last_history = []

    def log_response(self, response):
        """
        Every response is saved into self.log_list. Hook this for live
        data.
        """
        self.log_list += [response]

    def send_received(self):
        """Send the "Packet Received" Packet."""
        packet = PacketReceived()
        self.history += [(False, packet), ]
        logger.debug("> %r", packet)
        self.transport.send(packet.serialize(), no_wait=True)

    def handle_packet_response(self, packet, response):
        """A shortcut for calling the handle_response of the packet."""
        return packet.handle_response(response, self)

    def _transmit(self, packet, history):
        """
        Transmit the packet, go into slave mode and wait until the whole
        sequence is finished.
        """
        if not self.is_master or self.is_waiting:
            # raise TransmissionException(
            #     'Can\'t send until transmisson is ready')
            self.is_master = True

        else:
            self.is_master = False
        self.last = packet
        try:
            history += [(False, packet)]
            logger.debug("> %r", packet)
            success, response = self.transport.send(packet.serialize())
            response = Packet.parse(response)
            logger.debug("< %r", response)
            history += [(True, response)]
            # we sent the packet.
            # now lets wait until we get master back.
            if self.is_master:
                self.is_master = self.handle_packet_response(self.last, response)
            while not self.is_master:
                self.is_master = self.handle_packet_response(
                    self.last, response)
                if self.is_master:
                    break
                try:
                    success, response = self.transport.receive(
                        self.actual_timeout)
                    response = Packet.parse(response)
                    logger.debug("< %r", response)
                    history += [(True, response)]
                except TransportLayerException:
                    # some kind of timeout.
                    # if we are already master, we can bravely ignore this.
                    if self.is_master:
                        return TRANSMIT_OK
                    raise
                if self.is_master and success:
                    # we actually have to handle a last packet
                    stay_master = self.handle_packet_response(
                        packet, response)
                    logger.warning('Is Master Read Ahead happened.')
                    self.is_master = stay_master
        except Exception as e:
            self.is_master = True
            raise
        self.is_master = True
        return TRANSMIT_OK

    def transmit(self, packet, history=None):
        # we create a new history:
        self.last_history = history or []
        try:
            ret = self._transmit(packet, self.last_history)
            self.history += self.last_history
            return ret
        except Exception:
            self.history += self.last_history
            raise

    def transmit_cancel(self, packet, history=None):
        # we create a new history:
        self.last_history = history or []
        try:
            ret = self._abort(packet, self.last_history)
            self.history += self.last_history
            return ret
        except Exception:
            self.history += self.last_history
            raise

    def _abort(self, packet, history):
        """
        Transmit the packet, go into slave mode and wait until the whole
        sequence is finished.
        """
        # if not self.is_master or self.is_waiting:
        #     raise TransmissionException('Can\'t send until transmisson is ready')
        self.is_master = True
        self.last = packet
        try:
            history += [(False, packet)]
            logger.debug("> %r", packet)
            success, response = self.transport.send(packet.serialize())
            response = Packet.parse(response)
            logger.debug("< %r", response)
            history += [(True, response)]
            # we sent the packet.
            # now lets wait until we get master back.
            while self.is_master:
                self.is_master = self.handle_packet_response(
                    self.last, response)
                if self.is_master:
                    break
                # try:
                #     print("ABO _>>>>>>>", success, response, self.is_master)
                #     success, response = self.transport.receive(
                #         self.actual_timeout)
                #     response = Packet.parse(response)
                #     logger.debug("< %r", response)
                #     history += [(True, response)]
                # except TransportLayerException:
                #     print("EXCEPTION ------------->")
                #     # some kind of timeout.
                #     # if we are already master, we can bravely ignore this.
                #     if self.is_master:
                #         return TRANSMIT_OK
                #     raise
                if self.is_master and success:
                    # we actually have to handle a last packet
                    stay_master = self.handle_packet_response(
                        packet, response)
                    logger.warning('Is Master Read Ahead happened 1.')
                    self.is_master = stay_master
        except Exception as e:
            logger.warning(e)
            self.is_master = True
            raise
        self.is_master = True
        return TRANSMIT_OK
