#!/usr/bin/env python
# coding: utf-8

# In[13]:




# In[14]:


# A function I'll use later to extract FPGA resource usage stats from Yosys log output.
def print_stats(yosys_log):
    stat_start_line = yosys_log.grep(r'^2\.27\. ')
    stat_end_line = yosys_log.grep(r'^2\.28\. ')
    start_index = yosys_log.index(stat_start_line[0])
    end_index = yosys_log.index(stat_end_line[0])
    print('\n'.join(yosys_log[start_index+2:end_index-1]))


# **_Note_**: If you're reading this as a static HTML page, you can also get it as an
# executable Jupyter notebook [here](https://github.com/xesscorp/pygmyhdl/tree/master/examples).

# # Block (RAM) Party!

# I've already presented some simple combinational and sequential circuits using the FPGA's LUTs and D flip-flops.
# But the iCE40 has even more to offer: *block RAMs!*
# These are specialized blocks (hence the name) of high density [RAM](https://en.wikipedia.org/wiki/Random-access_memory)
# embedded within the FPGA fabric.
# These *BRAMs* provide a place to store lots of bits without using up all the DFFs in the FPGA.
# Now I'll show you how to use them.

# ## Inferring Block RAMs

# If you look at the
# [iCE40 technology library docs](http://www.latticesemi.com/~/media/LatticeSemi/Documents/TechnicalBriefs/iCE201404TechnologyLibrary.pdf?document_id=50524),
# you'll see how to instantiate a BRAM using Verilog or VHDL.
# But that doesn't do us much good since we're using MyHDL.
# So I'm going to demonstrate how to describe a RAM using MyHDL such that Yosys will *infer* that a BRAM is what I want.
# 
# As a first cut, here's a description of a simple RAM:

# In[15]:


from pygmyhdl import *

@chunk
def ram(clk_i, en_i, wr_i, addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:  Data is read/written on the rising edge of this clock input.
      en_i:   When high, the RAM is enabled for read/write operations.
      wr_i:   When high, data is written to the RAM; when low, data is read from the RAM.
      addr_i: Address bus for selecting which RAM location is being read/written.
      data_i: Data bus for writing data into the RAM.
    Outputs:
      data_o: Data bus for reading data from the RAM.
    '''
    
    # Create an array of words to act as RAM locations for storing data.
    # The number of bits in each word is set by the width of the data input bus.
    # The number of words is determined by the width of the address bus so,
    # for example, a 4-bit address would create 2**4 = 16 RAM locations.
    mem = [Bus(len(data_i)) for _ in range(2**len(addr_i))]
    
    # Perform read/write operations on the rising edge of the clock.
    @seq_logic(clk_i.posedge)
    def logic():
        if en_i:
            # The read/write operations only get executed if the enable input is high.
            if wr_i:
                # If the write-control is high, write the value on the input data bus
                # into the array of words at the given address value.
                mem[addr_i.val].next = data_i
            else:
                # If the write-control is low, read data from the word at the
                # given address value and send it to the output data bus.
                data_o.next = mem[addr_i.val]


# To verify this actually works as a RAM, I'll run a little simulation:

# In[16]:


initialize()  # Yeah, yeah, get things ready for simulation...

# Create wires and buses to connect to the RAM.
clk = Wire(name='clk')
en = Wire(name='en')
wr = Wire(name='wr')
addr = Bus(8, name='addr')
data_i = Bus(8, name='data_i')
data_o = Bus(8, name='data_o')

# Instantiate the RAM.
ram(clk_i=clk, en_i=en, wr_i=wr, addr_i=addr, data_i=data_i, data_o=data_o)

def ram_test_bench():
    '''RAM test bench: write 10 values to RAM, then read them back.'''
    
    en.next = 1  # Enable the RAM.
    
    # Write data to the first 10 locations in the RAM.
    wr.next = 1  # Enable writes to RAM.
    for i in range(10):
        addr.next = i            # Select RAM location to be written.
        data_i.next = 3 * i + 1  # Generate a value to write to the location.
        
        # Pulse the clock to write the data to RAM.
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

    # Read data from the 10 locations that were written.
    wr.next = 0  # Disable writes to RAM == enable reads from RAM.
    for i in range(10):
        addr.next = i   # Select the RAM location to be read.
        
        # Pulse the clock to read the data from RAM.
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

# Simulate the RAM using the test bench.
simulate(ram_test_bench())

# Look at the RAM inputs and outputs as the simulation was executed.
show_text_table('en clk wr addr data_i data_o')


# The simulation results show the values [1, 4, 7, 10, 13, 16, 19, 22, 25, 28] entering on the data input bus
# and being stored in the first ten RAM locations
# during the interval $t =$ [0, 19] when the write control input is high.
# Then the same set of data appears on the data output bus during $t =$ [20, 39] when the 
# first ten locations of the RAM are read back.
# So the RAM passes this simple simulation.
# 
# Now let's see how Yosys interprets this RAM description.
# First, I'll generate the Verilog code for a RAM with an eight-bit address bus ($2^8$ = 256 locations) with
# each word able to store an eight-bit byte.
# This works out to a total storage of 256&nbsp;$\times$&nbsp;8&nbsp;bits&nbsp;$=$&nbsp;2048&nbsp;bits.
# That should fit comfortably in a single, 4096-bit BRAM.

# In[17]:


toVHDL(ram, clk_i=Wire(), en_i=Wire(), wr_i=Wire(), addr_i=Bus(8), data_i=Bus(8), data_o=Bus(8))


# Next, I'll pass the Verilog code to Yosys and see what FPGA resources it uses:

# In[18]:





# Yowsa! It looks like Yosys is building the RAM from individual flip-flops -- 2056 of 'em.
# That's definitely not what we want.
# 
# The reason for the lousy implementation is that I haven't given Yosys a description that will
# trigger its RAM inference procedure.
# I searched and
# [found the following Verilog code](https://stackoverflow.com/questions/41499494/how-can-i-use-ice40-4k-block-ram-in-512x8-read-mode-with-icestorm)
# that *does* trigger Yosys:
# 
# ```
# module test(input clk, wen, input [8:0] addr, input [7:0] wdata, output reg [7:0] rdata);
#   reg [7:0] mem [0:511];
#   initial mem[0] = 255;
#   always @(posedge clk) begin
#         if (wen) mem[addr] <= wdata;
#         rdata <= mem[addr];
#   end
# endmodule
# ```
# 
# Then I just fiddled with my code until it produced something like that.
# It turns out the culprit is the presence of the enable input (`en_i`).
# Here's what happens if I take that out and leave the RAM enabled all the time:

# In[ ]:


@chunk
def ram(clk_i,wr_i, addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:  Data is read/written on the rising edge of this clock input.
      wr_i:   When high, data is written to the RAM; when low, data is read from the RAM.
      addr_i: Address bus for selecting which RAM location is being read/written.
      data_i: Data bus for writing data into the RAM.
    Outputs:
      data_o: Data bus for reading data from the RAM.
    '''
    
    mem = [Bus(len(data_i)) for _ in range(2**len(addr_i))]
    
    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[addr_i.val].next = data_i
        else:
            data_o.next = mem[addr_i.val]
                
toVHDL(ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(8), data_i=Bus(8), data_o=Bus(8))




# Now the statistics are much more reasonable: only a single block RAM is used.

# You can even remove the `else` clause and continually read out the RAM location at the current address:

# In[ ]:


@chunk
def simpler_ram(clk_i,wr_i, addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:  Data is read/written on the rising edge of this clock input.
      wr_i:   When high, data is written to the RAM; when low, data is read from the RAM.
      addr_i: Address bus for selecting which RAM location is being read/written.
      data_i: Data bus for writing data into the RAM.
    Outputs:
      data_o: Data bus for reading data from the RAM.
    '''
    
    mem = [Bus(len(data_i)) for _ in range(2**len(addr_i))]
    
    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[addr_i.val].next = data_i
        data_o.next = mem[addr_i.val]  # RAM address is always read out!
                
toVHDL(simpler_ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(8), data_i=Bus(8), data_o=Bus(8))




# This reduces the resource usage by a single LUT:

# The iCE40 BRAMs even allow a *dual-port* mode:
# a value can be written to one address while data is read from a second, independent address.
# (This is useful for building things like
# [FIFOs](https://en.wikipedia.org/wiki/FIFO_%28computing_and_electronics%29#Electronics).)

# In[ ]:


@chunk
def dualport_ram(clk_i, wr_i, wr_addr_i, rd_addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:     Data is read/written on the rising edge of this clock input.
      wr_i:      When high, data is written to the RAM; when low, data is read from the RAM.
      wr_addr_i: Address bus for selecting which RAM location is being written.
      rd_addr_i: Address bus for selecting which RAM location is being read.
      data_i:    Data bus for writing data into the RAM.
    Outputs:
      data_o:    Data bus for reading data from the RAM.
    '''
    
    mem = [Bus(len(data_i)) for _ in range(2**len(wr_addr_i))]
    
    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[wr_addr_i.val].next = data_i
        data_o.next = mem[rd_addr_i.val]  # Read from a different location than write.


# I'll run a simulation of the dual-port RAM similar to the one I did above,
# but here I'll start reading from the RAM before I finish writing data to it:

# In[ ]:


initialize()

# Create wires and buses to connect to the dual-port RAM.
clk = Wire(name='clk')
wr = Wire(name='wr')
wr_addr = Bus(8, name='wr_addr')  # Address bus for writes.
rd_addr = Bus(8, name='rd_addr')  # Second address bus for reads.
data_i = Bus(8, name='data_i')
data_o = Bus(8, name='data_o')

# Instantiate the RAM.
dualport_ram(clk_i=clk, wr_i=wr, wr_addr_i=wr_addr, rd_addr_i=rd_addr, data_i=data_i, data_o=data_o)

def ram_test_bench():
    for i in range(10):  # Perform 10 RAM writes and reads.
        
        # Write data to address i.
        wr_addr.next = i
        data_i.next = 3 * i + 1
        wr.next = 1
        
        # Read data from address i-3. After three clocks, the data that entered
        # on the data_i bus will start to appear on the data_o bus.
        rd_addr.next = i - 3
        
        # Pulse the clock to trigger the write and read operations.
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

# Simulate the RAM using the test bench.
simulate(ram_test_bench())

# Look at the RAM inputs and outputs as the simulation was executed.
show_text_table('clk wr wr_addr data_i rd_addr data_o')


# In the simulation output, you can see the value that entered the RAM through the `data_i` bus
# on the rising clock edge at time $t$ then exited on the `data_o` bus three clock cycles
# later at time $t + 6$.
# In this example, the dual-port RAM is acting as a simple [delay line](https://en.wikipedia.org/wiki/Digital_delay_line).

# ## Skinny RAM, Fat RAM

# In the previous section, I built a 256-byte RAM. Is that it? Is that *all* you can do with the block RAM?
# 
# Obviously not or else why would I even bring this up?
# Since block RAMs first appeared in FPGAs, the designers have allowed you to select the width of
# the data locations.
# While the number of data bits in the RAM is constant, you can clump them into different
# word sizes.
# Naturally, you'll get more addressable RAM locations if you use a narrow word width ("skinny" RAM)
# as compared to using wider words ("fat" RAM).
# Here are the allowable widths and the corresponding number of addressable locations 
# for the 4K BRAMs in the iCE40 FPGA:
# 
# | Data Width | # of Locations | Address Width |
# |:----------:|---------------:|:-------------:|
# | 2          | 2048           | 11            |
# | 4          | 1024           | 10            |
# | 8          | 512            |  9            |
# | 16         | 256            |  8            |
# 
# So how do you set the RAM width?
# Easy, just set the number of data bus bits and Yosys will select the smallest
# width that will hold it.
# For example, specifying a data width of seven bits will make Yosys choose a BRAM width of eight bits.
# Of course, that means you'll waste one bit of every memory location, but *c'est la vie*.
# 
# Specifying the number of addressable locations in the RAM is done similarly by setting the
# width of the address bus.
# To illustrate, an eleven-bit address bus would translate to $2^{11} =$ 2048 addressable locations.
# 
# Let's try some various word and address widths and see what Yosys does with them.
# First, here's a RAM with 512 ($2^9$) ten-bit words:

# In[ ]:


toVHDL(ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(9), data_i=Bus(10), data_o=Bus(10))



# Two BRAMs are used because a data width of sixteen bits is needed to hold the ten-bit words and a single 4K&nbsp;BRAM
# can only hold 256 of those.
# 
# What about a wide RAM with 128 ($2^7$) 24-bit words? That requires 3072 total bits so you would think that should fit
# into a single 4K BRAM, right?

# In[ ]:


toVHDL(ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(7), data_i=Bus(24), data_o=Bus(24))



# Since the maximum width of a single BRAM is sixteen bits,
# Yosys employs *two* BRAMs in parallel to get the entire 24-bit word width and then only uses half the
# addressable locations in each BRAM.
# Thus, a total of 8192 bits of BRAM is used to store the 3072 bits that were requested.
# 
# How about a 24-bit wide RAM with 512 words?
# That's 4$\times$ bigger than the previous one, so will it take 4$\times$ the number of BRAMs?

# In[ ]:


toVHDL(ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(9), data_i=Bus(24), data_o=Bus(24))



# Actually, it only takes *three* BRAMs instead of eight.
# Why is that?
# Because Yosys was able to stack two 256$\times$16 BRAMs to create a 512$\times$16 RAM, and then
# put this in parallel with a single 512$\times$8 BRAM to create a total 512$\times$24 RAM.
# 
# From these examples, you can see the efficiency with which you use BRAM resources
# is very dependent upon the RAM aspect-ratio (#locations $\times$ data width) that you specify,
# sometimes in unexpected ways.

# ## Demo Time!

# As I've said before, it would be a shame to do all this work and then not do something fun with it.
# So I'll show how to use a BRAM to record an on-off sequence of button presses and then play
# it back by lighting the iCEstick LEDs.
# (OK, maybe it's not *that* fun.)
# 
# Here's the basics of how the circuit operates:
# 
# 1. When button A is pressed and released, set the RAM address to 0 and start recording.
# 2. Every 0.01 seconds, sample the on-off value of button B, store it in RAM at the current address,
#    and increment the address.
# 3. If button A is not pressed, return to step 2 and take another sample.
#    Otherwise, store the current address to mark the end of the recording,
#    and halt here until button A is released.
# 4. When button A is released, reset the address to 0 (the start of the recording).
# 6. Every 0.01 seconds, read a button sample from the RAM and turn an LED on or off depending upon its value.
# 7. If the current address equals the end-of-recording address, reset the address to the beginning of the recording (address 0).
#    Otherwise, increment the current address.
# 8. If button A is not pressed, return to step 5 and display another sample.
#    Otherwise, loop back to step 1 and to start a new recording.
#    
# The iCEstick board already had the LEDs I needed, but no buttons.
# To fix that, I wired some external buttons to the board as shown in this schematic:
# 
# <img src="record_play_circuit.png" alt="Record/playback schematic." width="600px" />
# 
# Next, I broke the record/playback logic into four pieces:
# 
# 1. A RAM for storing the button samples (already coded above).
# 2. A counter that generates a *sampling pulse* every 0.01 seconds.
# 3. A controller that manages the recording/playback process.
# 4. A reset circuit that generates a single pulse to initialize the controller's state.
# 
# The MyHDL code for the circuit is shown below:

# In[ ]:


@chunk
def gen_reset(clk_i, reset_o):
    '''
    Generate a reset pulse to initialize everything.
    Inputs:
        clk_i:   Input clock.
    Outputs:
        reset_o: Active-high reset pulse.
    '''
    cntr = Bus(1)  # Reset counter.
    
    @seq_logic(clk_i.posedge)
    def logic():
        if cntr < 1:
            # Generate a reset while the counter is less than some threshold
            # and increment the counter.
            cntr.next = cntr.next + 1
            reset_o.next = 1
        else:
            # Release the reset once the counter passes the threshold and
            # stop incrementing the counter.
            reset_o.next = 0

@chunk
def sample_en(clk_i, do_sample_o, frq_in=12e6, frq_sample=100):
    '''
    Send out a pulse every so often to trigger a sampling operation.
    Inputs:
        clk_i:      Input clock.
        frq_in:     Frequency of the input clock (defaults to 12 MHz).
        frq_sample: Frequency of the sample clock (defaults to 100 Hz).
    Outputs:
        do_sample_o: Sends out a single-cycle pulse every 1/frq_sample seconds.
    '''
    # Compute the width of the counter and when it should roll-over based
    # on the master clock frequency and the desired sampling frequency.
    from math import ceil, log2
    rollover = int(ceil(frq_in / frq_sample)) - 1
    cntr = Bus(int(ceil(log2(frq_in/frq_sample))))
    
    # Sequential logic for generating the sampling pulse.
    @seq_logic(clk_i.posedge)
    def counter():
        cntr.next = cntr + 1         # Increment the counter.
        do_sample_o.next = 0         # Clear the sampling pulse output except...
        if cntr == rollover:
            do_sample_o.next = 1     # ...when the counter rolls over.
            cntr.next = 0 

@chunk
def record_play(clk_i, button_a, button_b, leds_o):
    '''
    Sample value on button B input, store in RAM, and playback by turning LEDs on/off.
    Inputs:
        clk_i:    Clock input.
        button_a: Button A input. High when pressed. Controls record/play operation.
        button_b: Button B input. High when pressed. Used to input samples for controlling LEDs.
    Outputs:
        leds_o:   LED outputs.
    '''
    
    # Instantiate the reset generator.
    reset = Wire()
    gen_reset(clk_i, reset)
    
    # Instantiate the sampling pulse generator.
    do_sample = Wire()
    sample_en(clk_i, do_sample)
    
    # Instantiate a RAM for holding the samples.
    wr = Wire()
    addr = Bus(11)
    end_addr = Bus(len(addr)) # Holds the last address of the recorded samples.
    data_i = Bus(1)
    data_o = Bus(1)
    ram(clk_i, wr, addr, data_i, data_o)
    
    # States of the record/playback controller.
    state = Bus(3)         # Holds the current state of the controller.
    INIT = 0               # Initialize. The reset pulse sends us here.
    WAITING_TO_RECORD = 1  # Getting read to record samples.
    RECORDING = 2          # Actually storing samples in RAM.
    WAITING_TO_PLAY = 3    # Getting ready to play back samples.
    PLAYING = 4            # Actually playing back samples.

    # Sequential logic for the record/playback controller.
    @seq_logic(clk_i.posedge)
    def fsm():
        
        wr.next = 0        # Keep the RAM write-control off by default.
        
        if reset:  # Initialize the controller using the pulse from the reset generator.
            state.next = INIT  # Go to the INIT state after the reset is released.
            
        elif do_sample:  # Process a sample whenever the sampling pulse arrives.
        
            if state == INIT:  # Initialize the controller.
                leds_o.next = 0b10101  # Light LEDs to indicate the INIT state.
                if button_a == 1:
                    # Get ready to start recording when button A is pressed.
                    state.next = WAITING_TO_RECORD  # Go to record setup state.
                    
            elif state == WAITING_TO_RECORD:  # Setup for recording.
                leds_o.next = 0b11010  # Light LEDs to indicate this state.
                if button_a == 0:
                    # Start recording once button A is released.
                    addr.next = 0           # Start recording from beginning of RAM.
                    data_i.next = button_b  # Record the state of button B.
                    wr.next = 1             # Write button B state to RAM.
                    state.next = RECORDING  # Go to recording state.
                    
            elif state == RECORDING:  # Record samples of button B to RAM.
                addr.next = addr + 1    # Next location for storing sample.
                data_i.next = button_b  # Sample state of button B.
                wr.next = 1             # Write button B state to RAM.
                # For feedback to the user, display the state of button B on the LEDs.
                leds_o.next = concat(1,button_b, button_b, button_b, button_b)
                if button_a == 1:
                    # If button A pressed, then get ready to play back the stored samples.
                    end_addr.next = addr+1  # Store the last sample address.
                    state.next = WAITING_TO_PLAY  # Go to playback setup state.
                    
            elif state == WAITING_TO_PLAY:  # Setup for playback.
                leds_o.next = 0b10000  # Light LEDs to indicate this state.
                if button_a == 0:
                    # Start playback once button A is released.
                    addr.next = 0         # Start playback from beginning of RAM.
                    state.next = PLAYING  # Go to playback state.
                    
            elif state == PLAYING:  # Show recorded state of button B on the LEDs.
                leds_o.next = concat(1,data_o[0],data_o[0],data_o[0],data_o[0])
                addr.next = addr + 1  # Advance to the next sample.
                if addr == end_addr:
                    # Loop back to the start of RAM if this is the last sample.
                    addr.next = 0
                if button_a == 1:
                    # Record a new sample if button A is pressed.
                    state.next = WAITING_TO_RECORD


# After converting the MyHDL to Verilog, I wrote the pin assignments for the LEDs and buttons to a file.
# I'm using all five LEDs on the iCEstick along with the
# two pushbuttons I connected to pins 114 and 118 of the FPGA through the iCEstick I/O header.

# In[ ]:


toVHDL(record_play, clk_i=Wire(), button_a=Wire(), button_b=Wire(), leds_o=Bus(5))

with open('record_play.pcf', 'w') as pcf:
    pcf.write(
'''
set_io clk_i 21
set_io leds_o[0] 99
set_io leds_o[1] 98
set_io leds_o[2] 97
set_io leds_o[3] 96
set_io leds_o[4] 95
set_io button_a 118
set_io button_b 114
'''
    )


# Finally, I synthesized, compiled, and downloaded the FPGA bitstream using the
# (by now) familiar sequence of commands:

# In[ ]:





# Once the bitstream was downloaded, I could store and playback a sequence of button pushes.
# It's difficult to describe using text or images, so here's a nice video of how it works:

# In[ ]:





# ## Summary
# 
# Once again, you've made it to the end of another ~~beating~~ tutorial.
# While battle-scarred and weary, your labors have earned you these treasures:
# 
# * How to write MyHDL that Yosys can recognize as a block RAM.
# 
# * How to read from and write to a RAM.
# 
# * How to create RAMs with various word widths and number of memory locations.
# 
# * How RAMs of different sizes are mapped into the fixed-size iCE40 BRAMs.
