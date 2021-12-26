
.PHONY: build
build:
	python3 litex-boards/litex_boards/targets/tinyfpga_bx.py --build --cpu-variant=lite

build_ecp5:
	python3 litex-boards/litex_boards/targets/lattice_ecp5_evn.py --build --load

build_debug:
	python3 litex-boards/litex_boards/targets/tinyfpga_bx.py --build --cpu-variant=lite+debug

build_demo:
	#litex_bare_metal_demo --build-path build/tinyfpga_bx
	(cd demo && SOC_DIRECTORY='../litex/litex/soc' BUILD_DIR=../build/tinyfpga_bx make)

build_demo_ecp5:
	(cd demo && SOC_DIRECTORY='../litex/litex/soc' BUILD_DIR=../build/lattice_ecp5_evn make)

flash_ecp5_bios:
	openFPGALoader -b ecpix5 build/lattice_ecp5_evn/software/bios/bios.bin -f --offset 0x400000

flash_ecp5_bitstream:
	openFPGALoader -b ecpix5 build/lattice_ecp5_evn/gateware/lattice_ecp5_evn.bit -f

flash_demo:
	sudo tinyprog -u demo/demo.bin


.PHONY: clean
clean:
	rm -r build/

flash:
	sudo tinyprog -p build/tinyfpga_bx/gateware/tinyfpga_bx.bin -u build/tinyfpga_bx/software/bios/bios.bin

flash_app:
	sudo tinyprog -u build/tinyfpga_bx/software/bios/bios.bin

terminal:
	picocom -b 112500 /dev/ttyUSB0

litex_term:
	litex_term /dev/ttyUSB2 --kernel demo/demo.bin

backup:
	cp Makefile github-remote/
	cp litex-boards/litex_boards/targets/lattice_ecp5_evn.py github-remote/targets/
	cp litex-boards/litex_boards/platforms/lattice_ecp5_evn.py github-remote/platforms/
	rsync -a --exclude '*.d' --exclude '*.o' --exclude '*.elf' demo/ github-remote/demo/

#openocd -f ecp5-evn.cfg -c "transport select jtag; init; svf build/lattice_ecp5_evn/gateware/lattice_ecp5_evn.svf; exit"

#openFPGALoader -b ecpix5 build/lattice_ecp5_evn/gateware/lattice_ecp5_evn.bit -f

#https://gojimmypi.blogspot.com/2020/03/litex-soft-cpu-on-ulx3s-reloading.html


# obsahuje boot z SPI FLASH namísto BRAM litex-boards/litex_boards/targets/sipeed_tang_nano_4k.py

# flash binárky
# openFPGALoader -b ecpix5 build/lattice_ecp5_evn/gateware/lattice_ecp5_evn.lpf -f --offset 0x400000
# Flash 16 MB, bitstream max 2.36 MB

#openFPGALoader -b ecpix5 build/lattice_ecp5_evn/software/bios/bios.bin -f --offset 0x400000

