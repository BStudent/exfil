# This module transmits the modulated and tuned IQ signal via SDR. If
# set to test mode, then the data is sent to a ZeroMQ sink through which
# it is routed to the receive side.
# Input:
#   - Tuned and modulated IQ data
# Output:
#   - IQ data sent to SDR

import rf_mgt as rfm
import zmq_utils as zmq
from gnuradio import gr
from gnuradio import blocks
from gnuradio import zeromq
from gnuradio import uhd
try:
    import osmosdr
except:
    print "Warning! No osmocom support detected. HackRF not available."


class TxOut(gr.hier_block2):
    def __init__(self,
                 rf_params,
                 tcp_test,
                 sdr_sel):
        gr.hier_block2.__init__(
            self,
            "TX Output",
            gr.io_signature(1, 1, gr.sizeof_gr_complex * 1),  # single in
            gr.io_signature(0, 0, 0)  # no streaming output
        )

        # parameters
        self.rf_params = rf_params
        self.tcp_test = tcp_test
        self.sdr_sel = sdr_sel

        # variables
        self.samp_rate = rf_params.samp_rate
        self.center_freq = rf_params.center_freq
        self.tx_gain = rf_params.tx_gain

        # choose the appropriate output
        if self.sdr_sel == rfm.HW_TEST:
            # send through a throttle block, otherwise test mode
            # will run too fast
            self.throttle = blocks.throttle(itemsize=gr.sizeof_gr_complex,
                                            samples_per_sec=self.samp_rate)
            self.connect((self, 0), (self.throttle, 0))

            # then into the zmq sink
            self.zeromq_push_sink_0 = zeromq.push_sink(
                gr.sizeof_gr_complex,
                1,
                self.tcp_test,
                100,
                False,
                -1)
            self.connect((self.throttle, 0), (self.zeromq_push_sink_0, 0))

        elif self.sdr_sel == rfm.HW_UHD:
            self.uhd_sink = uhd.usrp_sink(
                ",".join(("", "")),
                uhd.stream_args(
                        cpu_format="fc32",
                        channels=range(1),
                ),
            )
            self.uhd_sink.set_samp_rate(self.samp_rate)
            self.uhd_sink.set_center_freq(self.center_freq, 0)
            self.uhd_sink.set_gain(self.tx_gain, 0)
            self.uhd_sink.set_antenna('TX/RX', 0)
            self.connect((self, 0),  (self.uhd_sink))

        elif self.sdr_sel == rfm.HW_HACKRF:
            self.osmosdr_sink_0 = osmosdr.sink(args="numchan=" + str(1) + " " + '')
            self.osmosdr_sink_0.set_sample_rate(
                self.rf_params.samp_rate)
            self.osmosdr_sink_0.set_center_freq(
                self.rf_params.center_freq, 0)
            self.osmosdr_sink_0.set_freq_corr(0, 0)
            # mapping single value gain to hackrf's 3 stages as follows:
            #  Gain -> RF    IF     BB
            #   0      0     0      0
            #  20      0     8      8
            #  30      0    16     16
            #  40     14    16     16
            #  60     14    24     24
            #  80     14    32     32
            if   rf_params.tx_gain ==  0: rfg, ifg, bbg =  0,  0,  0
            elif rf_params.tx_gain == 20: rfg, ifg, bbg =  0, 20,  0
            elif rf_params.tx_gain == 30: rfg, ifg, bbg =  0, 30,  0
            elif rf_params.tx_gain == 40: rfg, ifg, bbg = 14, 26,  0
            elif rf_params.tx_gain == 60: rfg, ifg, bbg = 14, 46,  0
            elif rf_params.tx_gain == 80: rfg, ifg, bbg = 14, 66,  0
            else:                         rfg, ifg, bbg =  0, 30,  0
            self.osmosdr_sink_0.set_gain(rfg, 0)
            self.osmosdr_sink_0.set_if_gain(ifg, 0)
            self.osmosdr_sink_0.set_bb_gain(0, 0)
            self.osmosdr_sink_0.set_antenna('', 0)
            self.osmosdr_sink_0.set_bandwidth(0, 0)
            self.connect((self, 0), (self.osmosdr_sink_0, 0))

