import argparse
import os
import sys
import time

from mllpa import openSystem, generateModel, saveSystems, doVoro, saveVoro, readModelFile
from mllpa.interface_communication import _is_string
from mllpa.user_interface.cli_messages import _get_header, _get_footer, _main_message, _train_model_description, _train_model_usage, _read_phases_description, _read_phases_usage, _do_voronoi_description, _do_voronoi_usage, _read_model_description, _read_model_usage, _error_function_selection

##-\-\-\-\-\-\-\-\
## COMMON FUNCTIONS
##-/-/-/-/-/-/-/-/

# -------------------------------------
# Check if the given argument is a file
def _is_arg_file(parser, arg, extensions=['.gro'], exist=True):

    # Check if the file exists
    if exist and not os.path.isfile(arg):
        parser.error("The file "+str(arg)+" does not exist.")

    # Check if the extension is supported
    else:
        file_name, file_ext = os.path.splitext(arg)

        # Return error if not
        if file_ext not in extensions:
            parser.error("The extension "+str(file_ext)+" is not supported.")

        else:
            return arg

# -------------------------------------------------------
# Check if the given argument is a model file or a string
def _is_arg_model(parser, arg):

    # Check if the input is a file
    if os.path.isfile(arg):
        return _is_arg_file(parser, arg, extensions=['.lpm'], exist=True)

    # Check if it is a string
    elif not _is_string(arg):
        parser.error("The input "+str(arg)+" provided for the model is not supported.")

    else:
        return arg

# ------------------------------------------------------------
# Check that all the arguments of the list has the same length
def _len_lists(parser, ref_list, *args):

    # Get the length of the reference list
    ref_length = len(ref_list)

    # Check than all lists have the same length
    for arg_list in args:

        if len(arg_list) != ref_length:
            parser.error("The number of phases and input files does not match.")

##-\-\-\-\-\-\-\-\-\-\-\
## INTERFACING FUNCTIONS
##-/-/-/-/-/-/-/-/-/-/-/

# ---------------------------------
# Train a model on the given inputs
def _train_model(input_args):

    #=================#
    # PARSE ARGUMENTS #
    #=================#

    # Initialise the parser
    parser = argparse.ArgumentParser(description=_train_model_description(), usage=_train_model_usage())

    # REQUIRED ARGUMENTS

    # Coordinates files
    parser.add_argument("-c", "--coordinates", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.gro']), nargs='+',
        help="Coordinates files to open, use one per phase to train ML-LPA on.")

    # Structure files
    parser.add_argument("-s", "--structure", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.tpr']), nargs='+',
        help="Structure files to open, use one per phase to train ML-LPA on.")

    # Molecule type
    parser.add_argument("-mol", "--molecule_type", required=True,
        type=str,
        help="Name of the molecule type to train the models on.")

    # OPTIONAL ARGUMENTS

    # Phase labels
    parser.add_argument("-p", "--phases", required=False,
        type=str, default=['gel','fluid'], nargs='+',
        help="(Opt.) Labels of the phase to train the models on. Same order than for the files should be kept. Default: gel fluid.")

    # Trajectory file
    parser.add_argument("-t", "--trajectory", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.xtc']), nargs='+', default=None,
        help="(Opt.) Trajectory files to open, use one per phase to train ML-LPA on. Default is None.")

    # Begin trajectory scan
    parser.add_argument("-b", "--begin", required=False,
        type=int, default=0,
        help="(Opt.) First frame to read in the simulation. Default is 0.")

    # End trajectory scan
    parser.add_argument("-e", "--end", required=False,
        type=int, default=None,
        help="(Opt.) Last frame to read (+1) in the simulation. If None is provided, ML-LPA will read the trajectory till the end. Default is None.")

    # Step trajectory scan
    parser.add_argument("-step", "--step", required=False,
        type=int, default=1,
        help="(Opt.) Step used to read the trajectory. Default is 1.")

    # Output file
    parser.add_argument("-o", "--output_file", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.lpm'], exist=False), default=None,
        help="(Opt.) Name of the output file generated by the function. Default is auto-generation.")

    # SETTINGS

    # (Non-)heavy atoms
    parser.add_argument("-heavy", "--heavy_atoms", action="store_false",
        help="(Opt.) Include hydrogen atoms in the analysis when called.")

    # Rotate lipids up
    parser.add_argument("-up", "--rotate_up", action="store_false",
        help="(Opt.) Do not force lipid molecules to be orientated upward during the coordinates computation when called.")

    # Neighbor rank
    parser.add_argument("-rk", "--rank", required=False,
        type=int, default=6,
        help="(Opt.) Neighbor rank to use for the intra-molecular distances calculation. Default is 6.")

    # Validation size
    parser.add_argument("-vsize", "--validation_size", required=False,
        type=float, default=0.2,
        help="(Opt.) Size of the validation subset. Default is 0.2.")

    # Random seed
    parser.add_argument("-sd", "--random_seed", required=False,
        type=int, default=7,
        help="(Opt.) Seed for the random shuffling of the subsets for the training and verification. Default is 7.")

    # Number of repetitions
    parser.add_argument("-nr", "--number_repetitions", required=False,
        type=int, default=10,
        help="(Opt.) Number of time to repeat the shuffling and training to measure the score. Default is 10.")

    # Extract the user input
    args = parser.parse_args(input_args)

    # Check the length of the lists
    arg_lists = [args.phases, args.coordinates, args.structure]
    if args.trajectory is not None:
        arg_lists.append( args.trajectory )

    _len_lists(parser, *arg_lists)

    #=======================#
    # PROCESS THE FUNCTIONS #
    #=======================#

    # Load the files in the systems
    all_systems = []
    for i, phase_name in enumerate(args.phases):

        # Check the trajectory input
        trj_input = None
        if args.trajectory is not None:
            trj_input = args.trajectory[i]

        all_systems.append( openSystem(args.coordinates[i], args.structure[i], args.molecule_type, trj=trj_input, heavy=args.heavy_atoms, up=args.rotate_up, rank=args.rank, begin=args.begin, end=args.end, step=args.step) )

    # Generate the model
    generateModel( all_systems, phases=args.phases, file_path=args.output_file, validationSize=args.validation_size, seed=args.random_seed, nSplits=args.number_repetitions )

# ---------------------------------------
# Predict or set the phases of the system
def _read_phases(input_args):

    #=================#
    # PARSE ARGUMENTS #
    #=================#

    # Initialise the parser
    parser = argparse.ArgumentParser(description=_read_phases_description(), usage=_read_phases_usage())

    # REQUIRED ARGUMENTS

    # Coordinates files
    parser.add_argument("-c", "--coordinates", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.gro']),
        help="Coordinates file to process.")

    # Structure files
    parser.add_argument("-s", "--structure", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.tpr']),
        help="Structure file to process.")

    # Molecule type
    parser.add_argument("-mol", "--molecule_types", required=True,
        type=str, nargs='+',
        help="Name of the molecule types to analyse and label with phases.")

    # Phase models
    parser.add_argument("-m", "--models", required=True,
        type=lambda x: _is_arg_model(parser, x), nargs='+',
        help="Model files or static label to use to assign the phases to each molecule. Use one per molecule type to process.")

    # OPTIONAL ARGUMENTS

    # Trajectory file
    parser.add_argument("-t", "--trajectory", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.xtc']), default=None,
        help="(Opt.) Trajectory file to process. Default is None.")

    # Begin trajectory scan
    parser.add_argument("-b", "--begin", required=False,
        type=int, default=0,
        help="(Opt.) First frame to read in the simulation. Default is 0.")

    # End trajectory scan
    parser.add_argument("-e", "--end", required=False,
        type=int, default=None,
        help="(Opt.) Last frame to read (+1) in the simulation. If None is provided, ML-LPA will read the trajectory till the end. Default is None.")

    # Step trajectory scan
    parser.add_argument("-step", "--step", required=False,
        type=int, default=1,
        help="(Opt.) Step used to read the trajectory. Default is 1.")

    # Output file
    parser.add_argument("-o", "--output_file", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.csv', '.h5', '.xml'], exist=False), default=None,
        help="(Opt.) Name of the output file generated by the function. Default is auto-generation of a .csv file.")

    # SETTINGS

    # (Non-)heavy atoms
    parser.add_argument("-heavy", "--heavy_atoms", action="store_false",
        help="(Opt.) Include hydrogen atoms in the analysis when called.")

    # Rotate lipids up
    parser.add_argument("-up", "--rotate_up", action="store_false",
        help="(Opt.) Do not force lipid molecules to be orientated upward during the coordinates computation when called.")

    # Neighbor rank
    parser.add_argument("-rk", "--rank", required=False,
        type=int, default=6,
        help="(Opt.) Neighbor rank to use for the intra-molecular distances calculation. Default is 6.")

    # Extract the user input
    args = parser.parse_args(input_args)

    # Check the length of the lists
    arg_lists = [args.models, args.molecule_types]

    _len_lists(parser, *arg_lists)

    #=======================#
    # PROCESS THE FUNCTIONS #
    #=======================#

    # Load the files in the systems
    all_systems = []
    for i, type_name in enumerate(args.molecule_types):

        # Open the system
        current_system = openSystem(args.coordinates, args.structure, type_name, trj=args.trajectory, heavy=args.heavy_atoms, up=args.rotate_up, rank=args.rank, begin=args.begin, end=args.end, step=args.step)

        # Process the system to assign the phases
        if os.path.isfile(args.models[i]):
            current_system.getPhases(args.models[i])
        else:
            current_system.setPhases(args.models[i])

        # Store the processed system
        all_systems.append(current_system)

    # Save the systems in file
    saveSystems(all_systems, file_path=args.output_file)

# ----------------------------------------------
# Analyse the local environment of the molecules
def _read_environment(input_args):

    #=================#
    # PARSE ARGUMENTS #
    #=================#

    # Initialise the parser
    parser = argparse.ArgumentParser(description=_do_voronoi_description(), usage=_do_voronoi_usage())

    # REQUIRED ARGUMENTS

    # Coordinates files
    parser.add_argument("-c", "--coordinates", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.gro']),
        help="Coordinates file to process.")

    # Structure files
    parser.add_argument("-s", "--structure", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.tpr']),
        help="Structure file to process.")

    # Molecule type
    parser.add_argument("-mol", "--molecule_types", required=True,
        type=str, nargs='+',
        help="Name of the molecule types to analyse and label with phases.")

    # Phase models
    parser.add_argument("-m", "--models", required=True,
        type=lambda x: _is_arg_model(parser, x), nargs='+',
        help="Model files or static label to use to assign the phases to each molecule. Use one per molecule type to process.")

    # OPTIONAL ARGUMENTS

    # Trajectory file
    parser.add_argument("-t", "--trajectory", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.xtc']), default=None,
        help="(Opt.) Trajectory file to process. Default is None.")

    # Begin trajectory scan
    parser.add_argument("-b", "--begin", required=False,
        type=int, default=0,
        help="(Opt.) First frame to read in the simulation. Default is 0.")

    # End trajectory scan
    parser.add_argument("-e", "--end", required=False,
        type=int, default=None,
        help="(Opt.) Last frame to read (+1) in the simulation. If None is provided, ML-LPA will read the trajectory till the end. Default is None.")

    # Step trajectory scan
    parser.add_argument("-step", "--step", required=False,
        type=int, default=1,
        help="(Opt.) Step used to read the trajectory. Default is 1.")

    # Step trajectory scan
    parser.add_argument("-geo", "--geometry", required=False,
        type=str, default="bilayer",
        help="(Opt.) Geometry of the membrane to process. Default is bilayer.")

    # Exclude groups from ghosts
    parser.add_argument("-excl", "--exclude_ghosts", required=False,
        type=int, default=None, nargs='+',
        help="(Opt.) Indices of the molecule types to exclude from the ghost generation. Default is None.")

    # Output file
    parser.add_argument("-o", "--output_file", required=False,
        type=lambda x: _is_arg_file(parser, x, extensions=['.csv', '.h5', '.xml'], exist=False), default=None,
        help="(Opt.) Name of the output file generated by the function. Default is auto-generation of a .csv file.")

    # Process the local environment analysis
    parser.add_argument("-local", "--local_environment", action="store_false",
        help="(Opt.) Do not analyse the local environment of the molecules when called.")

    # SETTINGS

    # (Non-)heavy atoms
    parser.add_argument("-heavy", "--heavy_atoms", action="store_false",
        help="(Opt.) Include hydrogen atoms in the analysis when called.")

    # Rotate lipids up
    parser.add_argument("-up", "--rotate_up", action="store_false",
        help="(Opt.) Do not force lipid molecules to be orientated upward during the coordinates computation when called.")

    # Neighbor rank
    parser.add_argument("-rk", "--rank", required=False,
        type=int, default=6,
        help="(Opt.) Neighbor rank to use for the intra-molecular distances calculation. Default is 6.")

    # Neighbor threshold
    parser.add_argument("-th", "--threshold", required=False,
        type=float, default=0.01,
        help="(Opt.) Threshold for the spurious neighbors removal after tessellation. Default is 0.01.")

    # Extract the user input
    args = parser.parse_args(input_args)

    # Check the length of the lists
    arg_lists = [args.models, args.molecule_types]

    _len_lists(parser, *arg_lists)

    #=======================#
    # PROCESS THE FUNCTIONS #
    #=======================#

    # Load the files in the systems
    all_systems = []
    for i, type_name in enumerate(args.molecule_types):

        # Open the system
        current_system = openSystem(args.coordinates, args.structure, type_name, trj=args.trajectory, heavy=args.heavy_atoms, up=args.rotate_up, rank=args.rank, begin=args.begin, end=args.end, step=args.step)

        # Process the system to assign the phases
        if os.path.isfile(args.models[i]):
            current_system.getPhases(args.models[i])
        else:
            current_system.setPhases(args.models[i])

        # Store the processed system
        all_systems.append(current_system)

    # Tessellate the systems and read the local environment
    voronoi = doVoro(all_systems, args.geometry, threshold=args.threshold, exclude_ghosts=args.exclude_ghosts, read_neighbors=args.local_environment)

    # Save the results in file
    saveVoro(voronoi, file_path=args.output_file)

# ----------------------------------
# Read the content of the model file
def _read_model(input_args):

    #=================#
    # PARSE ARGUMENTS #
    #=================#

    # Initialise the parser
    parser = argparse.ArgumentParser(description=_read_model_description(), usage=_read_model_usage())

    # REQUIRED ARGUMENTS

    # Phase models
    parser.add_argument("-m", "--models", required=True,
        type=lambda x: _is_arg_file(parser, x, extensions=['.lpm']),
        help="Model files to read.")

    # Extract the user input
    args = parser.parse_args(input_args)

    #=======================#
    # PROCESS THE FUNCTIONS #
    #=======================#

    # Read the content of the file
    readModelFile(args.models, display=True)

##-\-\-\-\-\-\-\-\-\-\
## REPARTITION FUNCTION
##-/-/-/-/-/-/-/-/-/-/

# ---------------------------
# Select the function to load
def _select_function(function_name, input_args):

    # List the functions
    call_functions = {
    'train_model': _train_model,
    'read_phases': _read_phases,
    'do_voronoi': _read_environment,
    'read_model': _read_model
    }

    # Check if the function exists
    if function_name not in call_functions.keys():
        _error_function_selection(function_name)

    # Call the function and transfer the arguments
    call_functions[function_name](input_args)

# ------------------
# Get the user input
def main():

    # Display the header of the message
    start_time = time.time()
    print( _get_header() )

    # Display help
    if len(sys.argv) == 1:
        print(_main_message())

    # Go to the next function
    elif len(sys.argv) > 1:

        # Extract the function to call from the arguments
        function_name = sys.argv[1]
        input_args = sys.argv[2:]

        # Call the function
        _select_function(function_name, input_args)

    print( _get_footer(start_time) )
