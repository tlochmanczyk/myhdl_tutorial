#!/usr/bin/env python
# coding: utf-8

# In[1]:





# **_Note_**: If you're reading this as a static HTML page, you can also get it as an
# executable Jupyter notebook [here](https://github.com/xesscorp/pygmyhdl/tree/master/examples).

# # FSMs Without Monsters!

# If you google "FSM", you'll probably get links to "Flying Spaghetti Monster".
# But *that* is not *this*.
# Instead, I'm talking about [*finite-state machines*](https://en.wikipedia.org/wiki/Finite-state_machine).
# While some will tell you that working with FSMs is a monstrous chore, 
# it's really not any more difficult than working with combinational logic.
# (OK, maybe *that's* not very reassuring, either.)
# 
# At it's core, the FSM is a sequential circuit that remembers some stuff about what has happened
# in the past. This memory is called the *state* or *state variable* and it's stored in a bunch of flip-flops.
# As the FSM receives inputs (usually when a clock pulse occurs), 
# it combines them with the state variable to do two things:
# 
# * Generate some outputs to control some other piece of circuitry.
# * Update the state variable that records what it has done.
# 
# <img alt="FSM architecture." src="FSM_arch.png" width=600 />
# 
# Building an FSM typically involves three things:
# 
# * Figure out how to represent the state using flip-flops (this is often called *encoding*).
# * Design the logic that generates the outputs based on the inputs and the current state.
# * Design the logic that combines the inputs and the current state to arrive at the next state.
# 
# That's it. *That's all you have to do.* Now, you may have heard others talk about things like
# Mealy/Moore architectures or minimal state encoding or deterministic versus non-deterministic operation.
# **Fuhgeddaboudit!**
# The best way to learn about FSMs is to build some FSMs.
# After that (if you want), you can learn about these other topics and impress
# people with your pedantry.
# 
# To start off, let's take a circuit you already know about but maybe you didn't think of it as an FSM...

# ## A Counter

# We've used counters before. Here's one that's slightly modified to show it's also an FSM:

# In[2]:


from pygmyhdl import *

@chunk
def counter(clk_i, cnt_o):
    
    # Here's the counter state variable.
    cnt = Bus(len(cnt_o))
    
    # The next state logic is just an adder that adds 1 to the current cnt state variable.
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        cnt.next = cnt + 1
        
    # The output logic just sends the current cnt state variable to the output.
    @comb_logic
    def output_logic():
        cnt_o.next = cnt

initialize()
clk = Wire(name='clk')
cnt = Bus(3, name='cnt')
counter(clk_i=clk, cnt_o=cnt)
clk_sim(clk, num_cycles=10)
show_waveforms()


# You can see the output logic for the counter just copies the state variable to the counter outputs,
# and the next-state logic is an adder that increments the current counter value.
# 
# <img alt="Counter next-state and output logic." src="FSM_Counter.png" width=500 />

# This counter doesn't take any inputs except for the clock, so all it does is count from 0 to $N$, over and over.
# The next example adds a few inputs to make this FSM more exciting.

# ## A Counter With Reset and Enable Inputs

# The counter shown below has two additional inputs that affect how the state is updated on each rising clock edge:
# a *reset* to set the counter to a known state (usually with a value of zero), 
# and an *enable* that lets the counter advance when it's true and stalls the counter when it's false.

# In[3]:


@chunk
def counter_en_rst(clk_i, en_i, rst_i, cnt_o):
    
    cnt = Bus(len(cnt_o))
    
    # The next state logic now includes a reset input to clear the counter
    # to zero, and an enable input that only allows counting when it is true.
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if rst == True:
            cnt.next = 0
        elif en == True:
            cnt.next = cnt + 1
        else:
            # No reset and no enable, so just keep the counter at its current value.
            pass
        
    @comb_logic
    def output_logic():
        cnt_o.next = cnt

initialize()
clk = Wire(name='clk')
rst = Wire(1, name='rst')
en = Wire(1, name='en')
cnt = Bus(3, name='cnt')
counter_en_rst(clk_i=clk, rst_i=rst, en_i=en, cnt_o=cnt)

def cntr_tb():
    '''Test bench for the counter with a reset and enable inputs.'''
    
    # Enable the counter for a few cycles.
    rst.next = 0
    en.next = 1
    for _ in range(4):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        
    # Disable the counter for a few cycles.
    en.next = 0
    for _ in range(2):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

    # Re-enable the counter for a few cycles.
    en.next = 1
    for _ in range(2):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
    
    # Reset the counter.
    rst.next = 1
    clk.next = 0
    yield delay(1)
    clk.next = 1
    yield delay(1)
    
    # Start counting again.
    rst.next = 0
    for _ in range(4):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        
simulate(cntr_tb())
show_waveforms(tick=True)


# You can see that lowering the enable input over the interval [8, 12] keeps the counter from advancing, and
# raising the reset at $t=$ 16 forces the counter back to zero.
# 
# This is all well and good, but you've known how to build counters for a quite a while.
# Let's look at an FSM that does something new.

# ## A Button Debouncer

# We used buttons previously in the block RAM demonstration circuit.
# Buttons, being the mechanical beasts they are, have an annoying habit of
# [*chattering* or *bouncing*](https://www.allaboutcircuits.com/technical-articles/switch-bounce-how-to-deal-with-it/)
# as their metal contacts bash into one another and rebound until they settle.
# This is seen by the rest of the circuitry as a sequence of rapid button presses, even if
# the person thinks they only pressed the button once.
# 
# There are many solutions to this problem, but I'll show an FPGA circuit that does it
# (because that's the hammer I'm swinging).
# Essentially, the circuit filters out button bounces by waiting until the button has had a stable value
# for a certain amount of time and then outputing that value like so:
# 
# 1. The circuit compares the current value of the button input to the previous value stored in a flip-flop.
# 2. If the values match, a counter is decremented. But if the values don't match, the counter is
#    reset to a non-zero value.
# 3. If the counter reaches zero, the button value must not have changed for a while. This stable button value
#    is output by the circuit. If the counter is non-zero, the previous stable button value is retained on the output.
# 
# Here's code for an FSM that does this:

# In[4]:


@chunk
def debouncer(clk_i, button_i, button_o, debounce_time):
    '''
    Inputs:
        clk_i: Main clock input.
        button_i: Raw button input.
        button_o: Debounced button output.
        debounce_time: Number of clock cycles the button value has to be stable.
    '''

    # These are the state variables of the FSM.
    from math import ceil, log2
    debounce_cnt = Bus(int(ceil(log2(debounce_time+1))), name='dbcnt')  # Counter big enough to store debounce time.
    prev_button = Wire(name='prev_button')  # Stores the button value from the previous clock cycle.
    
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if button_i == prev_button:
            # If the current and previous button values are the same, decrement the counter
            # until it reaches zero and then stop.
            if debounce_cnt != 0:
                debounce_cnt.next = debounce_cnt - 1
        else:
            # If the current and previous button values aren't the same, then the button must
            # still be bouncing so reset the counter to the debounce interval and try again.
            debounce_cnt.next = debounce_time
            
        # Store the current button value for comparison during the next clock cycle.
        prev_button.next = button_i
        
    @seq_logic(clk_i.posedge)
    def output_logic():
        if debounce_cnt == 0:
            # Output the stable button value whenever the counter is zero.
            # Don't use the actual button input value because that could change at any time.
            button_o.next = prev_button


# Now I can simulate button presses of various lengths and watch the output of the circuit.
# Note that I'm using a very small debounce time to keep the simulation to a reasonable length.
# In reality, a clock of 12 MHz and a debounce time of 100 ms would require a debounce count of 1,200,000.

# In[5]:


initialize()  # Initialize for simulation here because we'll be watching the internal debounce counter.

clk = Wire(name='clk')
button_i = Wire(name='button_i')
button_o = Wire(name='button_o')
debouncer(clk, button_i, button_o, 3)

def debounce_tb():
    '''Test bench for the counter with a reset and enable inputs.'''
    
    # Initialize the button and leave it stable for the debounce time.
    button_i.next = 1
    for _ in range(4):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
    
    # Blip the button for less than the debounce time and show the debounced output does not change.
    button_i.next = 0
    for _ in range(2):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
    button_i.next = 1
    for _ in range(2):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
    
    # Press the button for more than the debounce time and show the debounced output changes.
    button_i.next = 0
    for _ in range(5):
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        
simulate(debounce_tb())
show_waveforms(tick=True)            


# Note these points in the simulation:
# 
# * The debounce counter gets reset to its maximum value when the current and previous button values are different
#   ($t =$ 1, 9, 13, 17).
# * The initial button press during interval [0, 8] is long enough to change the button output at $t =$ 9.
#   The button release for $t \ge$ 16 is also long enough to change the button output at $t =$ 25.
# * Neither of the short release and press intervals from $t =$ 8 to $t =$ 16 are long enough for the debounce counter
#   to reach zero and trigger a button output.

# Maybe these past few examples don't feel like state machines, but they are.
# They each store some information about the past and use it to change their behavior in the present.
# But, possibly, you're looking for something more like the classic state machines you've seen in books.
# Well, I'm never one to disappoint!

# ## A "Classic" State Machine

# This FSM has four states, two inputs, and four outputs.
# The states are arranged like a ring, with transistions going from each state to the states preceding and following it.
# When the first input is active, the FSM transitions forward (clockwise) by one state; when the
# second input is active, the FSM moves one state backward (counter-clockwise).
# Finally, a single output is associated with each state that is high whenever the FSM is in that state.
# 
# <img src="classic_FSM_diag.png" alt="Classic FSM state diagram." width="400" />

# The MyHDL code for this FSM is shown below.
# As you'll see, each possible state is allocated a section of code that describes what state the FSM will go to
# for all possible combinations of the inputs.

# In[6]:


@chunk
def classic_fsm(clk_i, inputs_i, outputs_o):
    '''
    Inputs:
        clk_i: Main clock input.
        inputs_i: Two-bit input vector directs state transitions.
        outputs_o: Four-bit output vector.
    '''
    
    # Declare a state variable with four states. In addition to the current
    # state of the FSM, the state variable also stores a complete list of its
    # possible values to use for comparing what state the FSM is in and for
    # assigning a new state.
    fsm_state = State('A', 'B', 'C', 'D', name='state')

    # This counter is used to apply a reset to the FSM for the first few clocks upon startup.
    reset_cnt = Bus(2)
        
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if reset_cnt < reset_cnt.max-1:
            # The reset counter starts at zero upon startup. The FSM stays in this reset
            # state until the counter increments to its maximum value. Then it never returns here.
            reset_cnt.next = reset_cnt + 1
            fsm_state.next = fsm_state.s.A  # Set initial state for FSM after reset.
        elif fsm_state == fsm_state.s.A:  # Compare current state to state A.
            # If the FSM is in state A, then go forward to state B if inputs_i[0] is active,
            # otherwise go backward to state D if inputs_i[1] is active.
            # Stay in this state if neither input is active.
            if inputs_i[0]:
                fsm_state.next = fsm_state.s.B   # Update state to state B.
            elif inputs_i[1]:
                fsm_state.next = fsm_state.s.D   # Update state to state D.
        elif fsm_state == fsm_state.s.B:
            # State B operates similarly to state A.
            if inputs_i[0]:
                fsm_state.next = fsm_state.s.C
            elif inputs_i[1]:
                fsm_state.next = fsm_state.s.A
        elif fsm_state == fsm_state.s.C:
            # State C operates similarly to states A and B.
            if inputs_i[0]:
                fsm_state.next = fsm_state.s.D
            elif inputs_i[1]:
                fsm_state.next = fsm_state.s.B
        elif fsm_state == fsm_state.s.D:
            # State D yada, yada...
            if inputs_i[0]:
                fsm_state.next = fsm_state.s.A
            elif inputs_i[1]:
                fsm_state.next = fsm_state.s.C
        else:
            # If the FSM is in some unknown state, send it back to the starting state.
            fsm_state.next = fsm_state.s.A
                
    @comb_logic
    def output_logic():
        # Turn on one of the outputs depending upon which state the FSM is in.
        if fsm_state == fsm_state.s.A:
            outputs_o.next = 0b0001
        elif fsm_state == fsm_state.s.B:
            outputs_o.next = 0b0010
        elif fsm_state == fsm_state.s.C:
            outputs_o.next = 0b0100
        elif fsm_state == fsm_state.s.D:
            outputs_o.next = 0b1000
        else:
            # Turn on all the outputs if the FSM is in some unknown state (shouldn't happen).
            outputs_o.next = 0b1111


# Now I can stimulate the FSM with the following test bench.
# The FSM is moved forward by three states and then backward three times, so it should end up where it started.

# In[7]:


initialize()

inputs = Bus(2, name='inputs')
outputs = Bus(4, name='outputs')
clk = Wire(name='clk')
classic_fsm(clk, inputs, outputs)

def fsm_tb():
    nop = 0b00  # no operation - both inputs are inactive
    fwd = 0b01  # Input combination for moving forward.
    bck = 0b10  # Input combination for moving backward.

    # Input sequence of 3 forwards and 3 backwards transitions.
    # The four initial NOPs are for the FSM's initial reset period.
    ins = [nop, nop, nop, nop, fwd, fwd, fwd, bck, bck, bck]
    
    # Apply each input combination from the list and then pulse the clock.
    for inputs.next in ins:
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        
simulate(fsm_tb())
show_waveforms('clk inputs state outputs', tick=True)


# The waveforms show the FSM moving forward (`A` $\rightarrow$ `B` $\rightarrow$ `C` $\rightarrow$ `D`) and then 
# moving back to where it started (`D` $\rightarrow$ `C` $\rightarrow$ `B` $\rightarrow$ `A`).
# This is good, but what if your inputs are slow (like from manually-operated pushbuttons)
# and your clock is very fast (like 12 MHz).
# Then it would be hard to make controlled state transitions because a single button press would cause
# many state changes.
# 
# In this case, the solution is to make the FSM change states *only* when the input changes from a 0 (inactive)
# to a 1 (active).
# This is easy to do by comparing the current values of the inputs with their values on the previous clock cycle.
# When they are different, the FSM can make a transition.

# In[8]:


@chunk
def classic_fsm(clk_i, inputs_i, outputs_o):

    fsm_state = State('A', 'B', 'C', 'D', name='state')
    reset_cnt = Bus(2)
    
    # Variables for storing the input values during the previous clock
    # and holding the changes between the current and previous input values.
    prev_inputs = Bus(len(inputs_i), name='prev_inputs')
    input_chgs = Bus(len(inputs_i), name='input_chgs')
    
    # This logic compares the current input values with the negation of the previous values.
    # The output is active only if an input goes from 0 to 1.
    @comb_logic
    def detect_chg():
        input_chgs.next = inputs_i & ~prev_inputs
        
    # This is the same FSM state transition logic as before, except it looks at the
    # input_chgs signals instead of the input_i signals.
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if reset_cnt < reset_cnt.max-1:
            reset_cnt.next = reset_cnt + 1
            fsm_state.next = fsm_state.s.A
        elif fsm_state == fsm_state.s.A:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.B
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.D
        elif fsm_state == fsm_state.s.B:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.C
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.A
        elif fsm_state == fsm_state.s.C:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.D
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.B
        elif fsm_state == fsm_state.s.D:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.A
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.C
        else:
            fsm_state.next = fsm_state.s.A
            
        prev_inputs.next = inputs_i  # Record the current input values.
                
    @comb_logic
    def output_logic():
        if fsm_state == fsm_state.s.A:
            outputs_o.next = 0b0001
        elif fsm_state == fsm_state.s.B:
            outputs_o.next = 0b0010
        elif fsm_state == fsm_state.s.C:
            outputs_o.next = 0b0100
        elif fsm_state == fsm_state.s.D:
            outputs_o.next = 0b1000
        else:
            outputs_o.next = 0b1111 


# Now I'll modify the test bench a bit by adding another sequence of inputs that alternate
# between active and inactive values.

# In[9]:


initialize()

inputs = Bus(2, name='inputs')
outputs = Bus(4, name='outputs')
clk = Wire(name='clk')
classic_fsm(clk, inputs, outputs)

def fsm_tb():
    nop = 0b00
    fwd = 0b01
    bck = 0b10
    
    ins = [nop, nop, nop, nop, fwd, fwd, fwd, bck, bck, bck]
    for inputs.next in ins:
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

    # Interspersed active and inactive inputs.
    ins = [fwd, nop, fwd, nop, fwd, nop, bck, nop, bck, nop, bck, nop]
    for inputs.next in ins:
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        
simulate(fsm_tb())
show_waveforms('clk inputs prev_inputs input_chgs state outputs', tick=True, width=2000)


# From the simulation, you can see the first sequence of six inputs (time $t =$ 8 to $t =$ 20) only caused two state transitions
# (`A` $\rightarrow$ `B` $\rightarrow$ `A`) because the inputs only changed twice.
# Then, when active inputs were interspersed with inactive inputs (time $t \ge$ 20), the FSM went through six state transitions
# (`A` $\rightarrow$ `B` $\rightarrow$ `C` $\rightarrow$ `D` $\rightarrow$ `C` $\rightarrow$ `B` $\rightarrow$ `A`)

# ## Demo Time!

# Once again, we've reached the highly-anticipated demo time!
# This time, I'm just going to hook the previous FSM to two pushbuttons and four LEDs
# and then steer it through a few state transitions.

# In[10]:


toVHDL(classic_fsm, clk_i=Wire(), inputs_i=Bus(2), outputs_o=Bus(4))

with open('classic_fsm.pcf', 'w') as pcf:
    pcf.write(
'''
set_io clk_i 21
set_io outputs_o[0] 99
set_io outputs_o[1] 98
set_io outputs_o[2] 97
set_io outputs_o[3] 96
set_io inputs_i[0] 118
set_io inputs_i[1] 114
'''
    )




# The following video shows the operation of the FSM on the iCEstick board.
# As you watch, you can see the FSM move backwards and forwards through the states under the guidance
# of the button presses.
# However, there are times when it makes multiple transitions for a single button press because the buttons are bouncing.

# In[11]:




# To correct the button bounce problem, I added debounce circuits to the FSM as shown below.

# In[12]:


@chunk
def classic_fsm(clk_i, inputs_i, outputs_o):

    fsm_state = State('A', 'B', 'C', 'D', name='state')
    reset_cnt = Bus(2)
    
    prev_inputs = Bus(len(inputs_i), name='prev_inputs')
    input_chgs = Bus(len(inputs_i), name='input_chgs')

    # Take the inputs and run them through the debounce circuits.
    dbnc_inputs = Bus(len(inputs_i))  # These are the inputs after debouncing.
    debounce_time = 120000
    debouncer(clk_i, inputs_i.o[0], dbnc_inputs.i[0], debounce_time)
    debouncer(clk_i, inputs_i.o[1], dbnc_inputs.i[1], debounce_time)

    # The edge detection of the inputs is now performed on the debounced inputs.
    @comb_logic
    def detect_chg():
        input_chgs.next = dbnc_inputs & ~prev_inputs
        
    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if reset_cnt < reset_cnt.max-1:
            fsm_state.next = fsm_state.s.A
            reset_cnt.next = reset_cnt + 1
        elif fsm_state == fsm_state.s.A:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.B
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.D
        elif fsm_state == fsm_state.s.B:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.C
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.A
        elif fsm_state == fsm_state.s.C:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.D
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.B
        elif fsm_state == fsm_state.s.D:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.A
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.C
        else:
            fsm_state.next = fsm_state.s.A

        prev_inputs.next = dbnc_inputs  # Store the debounced inputs.
                
    @comb_logic
    def output_logic():
        if fsm_state == fsm_state.s.A:
            outputs_o.next = 0b0001
        elif fsm_state == fsm_state.s.B:
            outputs_o.next = 0b0010
        elif fsm_state == fsm_state.s.C:
            outputs_o.next = 0b0100
        elif fsm_state == fsm_state.s.D:
            outputs_o.next = 0b1000
        else:
            outputs_o.next = 0b1111


# Now it's just a matter of recompiling the debounced FSM and observing its operation.

# In[13]:


toVHDL(classic_fsm, clk_i=Wire(), inputs_i=Bus(2), outputs_o=Bus(4))

with open('classic_fsm.pcf', 'w') as pcf:
    pcf.write(
'''
set_io clk_i 21
set_io outputs_o[0] 99
set_io outputs_o[1] 98
set_io outputs_o[2] 97
set_io outputs_o[3] 96
set_io inputs_i[0] 118
set_io inputs_i[1] 114
'''
    )




# I probably don't have to tell you that the bouncing buttons are conspicuously absent in the following video.

# In[14]:




# ## Summary
# 
# Once more we must part ways, but hopefully I've left you with the following nuggets of information:
# 
# * FSMs are digital circuits that store knowledge from the past in order to affect their behavior in the present.
# 
# * Some common circuits you already knew are actually FSMs (like counters).
# 
# * Mechanical buttons can bounce and FSMs can be used to debounce them.
# 
# * Classic state machine diagrams are relatively easy to translate into MyHDL.
