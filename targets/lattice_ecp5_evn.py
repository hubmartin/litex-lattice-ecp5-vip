#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex_boards.platforms import ecp5_evn

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.cores.led import LedChaser, WS2812

from litedram.modules import MT41J128M16
from litedram.phy import ECP5DDRPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys = ClockDomain()

        # # #

        # clk / rst
        clk27 = platform.request("clk27")
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")

        # pll
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)


class _CRGSDRAM(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_init    = ClockDomain()
        self.clock_domains.cd_por     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys     = ClockDomain()
        self.clock_domains.cd_sys2x   = ClockDomain()
        self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.stop  = Signal()
        self.reset = Signal()

        # Clk / Rst
        clk27 = platform.request("clk27")
        rst_n = platform.request("rst_n")

        # PLL
        sys2x_clk_ecsout = Signal()
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk27, 27e6)
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init,   25e6)
        self.specials += [
            Instance("ECLKBRIDGECS",
                i_CLK0   = self.cd_sys2x_i.clk,
                i_SEL    = 0,
                o_ECSOUT = sys2x_clk_ecsout,
            ),
            Instance("ECLKSYNCB",
                i_ECLKI = sys2x_clk_ecsout,
                i_STOP  = self.stop,
                o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = 0,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = self.reset,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys,    ~pll.locked | self.reset),
            AsyncResetSynchronizer(self.cd_sys2x,  ~pll.locked | self.reset),
        ]


# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    mem_map = {**SoCCore.mem_map, **{"spiflash": 0x1000000}}
    def __init__(self, sys_clk_freq=int(50e6), x5_clk_freq=None, toolchain="trellis",
                 with_led_chaser=True, **kwargs):
        platform = ecp5_evn.Platform(toolchain=toolchain)


        bios_flash_offset = 0x400000

        # Set CPU variant / reset address
        kwargs["cpu_reset_address"] = self.mem_map["spiflash"] + bios_flash_offset
        kwargs["integrated_rom_size"] = 0

        #kwargs["integrated_main_ram_size"] = 0

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = "LiteX SoC on ECP5 Evaluation Board",
            ident_version  = True,
            #integrated_main_ram_size = 0x4000,
            integrated_main_ram_size = 0,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        crg_cls = _CRG
        #crg_cls = _CRGSDRAM #if not self.integrated_main_ram_size else _CRG
        #crg_cls = _CRGSDRAM if not self.integrated_main_ram_size else _CRG
        self.submodules.crg = crg_cls(platform, sys_clk_freq)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if self.integrated_main_ram_size:
            self.submodules.ddrphy = ECP5DDRPHY(
                platform.request("ddram"),
                sys_clk_freq=sys_clk_freq)
            self.comb += self.crg.stop.eq(self.ddrphy.init.stop)
            self.comb += self.crg.reset.eq(self.ddrphy.init.reset)
            self.add_sdram("sdram",
                phy           = self.ddrphy,
                module        = MT41J128M16(sys_clk_freq, "1:2"),
                l2_cache_size = kwargs.get("l2_size", 8192),
            )

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.submodules.leds = LedChaser(
                pads         = platform.request_all("user_led"),
                sys_clk_freq = sys_clk_freq)

        # WS2812
        self.submodules.ws2812 = WS2812(platform.request("ws2812"), nleds=4, sys_clk_freq=sys_clk_freq)
        self.bus.add_slave(name="ws2812", slave=self.ws2812.bus, region=SoCRegion(
            origin = 0x2000_0000,
            size   = 4*4,
        ))

        # SPI Flash --------------------------------------------------------------------------------
        from litespi.modules import MX25L12835F
        from litespi.opcodes import SpiNorFlashOpCodes as Codes
        self.add_spi_flash(mode="1x", module=MX25L12835F(Codes.READ_1_1_1), with_master=False)

        # Add ROM linker region --------------------------------------------------------------------
        self.bus.add_region("rom", SoCRegion(
            origin = self.mem_map["spiflash"] + bios_flash_offset,
            size   = (16-4)*1024*1024,
            linker = True)
        )

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on ECP5 Evaluation Board")
    parser.add_argument("--build",        action="store_true", help="Build bitstream")
    parser.add_argument("--load",         action="store_true", help="Load bitstream")
    parser.add_argument("--toolchain",    default="trellis",   help="FPGA toolchain: trellis (default) or diamond")
    parser.add_argument("--sys-clk-freq", default=80e6,        help="System clock frequency (default: 60MHz)")
    parser.add_argument("--x5-clk-freq",  type=int,            help="Use X5 oscillator as system clock at the specified frequency")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(toolchain=args.toolchain,
        sys_clk_freq = int(float(args.sys_clk_freq)),
        x5_clk_freq  = args.x5_clk_freq,
        **soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".svf"))

if __name__ == "__main__":
    main()