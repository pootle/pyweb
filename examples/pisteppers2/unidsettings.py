#!/usr/bin/python3

import stepgenconstacc as sg

drivepins=(15,22,27,17)

singlebang=(
    'onoff',
    ((1,0,0,0),
     (0,1,0,0),
     (0,0,1,0),
     (0,0,0,1))
)

smoothbang=(
    'onoff',
    ((1,0,0,0),
     (1,1,0,0),
     (0,1,0,0),
     (0,1,1,0),
     (0,0,1,0),
     (0,0,1,1),
     (0,0,0,1),
     (1,0,0,1))
)

pairbang=(
    'onoff', 
    ((1,1,0,0),
     (0,1,1,0),
     (0,0,1,1),
     (1,0,0,1))
)

swustep_tables=(   # power settings for the 4 pins for various step modes
       ( 'pwm',
        ((128, 0, 0, 0),
         (96, 32, 0, 0),
         (64, 64, 0, 0),
         (32, 96,0,0),
         (0,128,0,0),
         (0,96, 32, 0),
         (0, 64, 64, 0),
         (0, 32, 96, 0),
         (0, 0, 128,0),
         (0,0,96,32),
         (0,0,64,64),
         (0,0,32,96),
         (0,0,0,128),
         (32, 0, 0, 96),
         (64,0,0,64),
         (96, 0, 0, 32)),
         25,
         4
       ),
       ( 'pwm',
         ((255, 0, 0, 0), 
         (128,128, 0, 0), 
         (0,255, 0, 0),
         (0, 128, 128, 0),
         (0, 0, 255, 0),
         (0, 0, 128, 128),
         (0, 0, 0, 255),
         (128, 0, 0, 128)),
         50,
         2
      ),
      ( 'block',
         pairbang[1],
         99999,
         1)
)

multi_dmaustep_tables = (
    ('block', 
      smoothbang[1],
      35,
      2),
     ('block',
      singlebang[1],
      60,
      1),
    ( 'block',
      pairbang[1],
      999999,     # set last entry to beyond fastest ever speed - motor's max_tps limits the speed
      1),
)

single_dmaustep_tables = (
    ( 'block',
      smoothbang[1],
      99999,
      2),         # set last entry to beyond fastest ever speed - motor's max_tps limits the speed
)


# byj max speeds
# singlebang - 750 tps, but minimal load stalls motor
#              500 tps - reliable start
# pairbang same as singlebang
# smoothbang   1050, minimal load stalls


stepping_params={
    'slow': {
        'drive_mode'    : 'soft',
        'step_tables'   : swustep_tables,    # the step tables are pre-processed into a new entry 'prep_tables' in the motor constructors
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 10,
            'max_tps'       : 300,
            'accel_tps'     : 100,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
    'fast1': {
        'drive_mode'    : 'dma',
        'step_tables'   : single_dmaustep_tables,
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 10,
            'max_tps'       : 1000,
            'accel_tps'     : 200,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
    'fast2': {
        'drive_mode'    : 'dma',
        'step_tables'   : multi_dmaustep_tables,
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 10,
            'max_tps'       : 1000,
            'accel_tps'     : 200,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
    'dma single': {
        'drive_mode'    : 'dma',
        'step_tables'   : (
                ( 'block',
                  singlebang[1],
                  99999,
                  1),),
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 5,
            'max_tps'       : 700,
            'accel_tps'     : 20,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
    'dma smooth': {
        'drive_mode'    : 'dma',
        'step_tables'   : (
                ( 'block',
                  smoothbang[1],
                  99999,
                  2),),
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 50,
            'max_tps'       : 1000,
            'accel_tps'     : 50,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
    'dma_pair': {
        'drive_mode'    : 'dma',
        'step_tables'   : (
                ( 'block',
                  pairbang[1],
                  99999,
                  1),),
        'hold_timeout'  : 1.5,
        'hold_power'    : 0,
        'stepgen_class' : sg.stepconstacc,
        'stepgen_params': {
            'start_tps'     : 5,
            'max_tps'       : 700,
            'accel_tps'     : 20,
            'dir_delay'     : .001,
            'hold_tick'     : .7,
            'ustep_factor'  : 4,
            }
        },
}