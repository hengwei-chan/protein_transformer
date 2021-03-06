import os

ERROR_CODES = [("SEQUENCE_ERRORS", "structures failed because of an unresolvable issue with sequences."),
               ("MULTIPLE_CONTIG_ERRORS", "structures failed to parse because they had ambiguous sequence "
                                          "alignments/multiple identical contigs."),
               ("FAILED_ASTRAL_IDS", "Astral IDs failed to parse for some unknown reason."),
               ("TEST_PARSING_ERRORS", "test structures experience AttributeErrors when parsing."),
               ("NSAA_ERRORS", "structures failed because they had non-standard amino acids."),
               ("MISSING_ASTRAL_IDS", "Astral IDs could not be found in the lookup file."),
               ("SHORT_ERRORS", "structures failed because they were too short."),
               ("PARSING_ERROR_ATTRIBUTE", "structures experienced AttributeErrors when parsing PDB/mmCIF files."),
               ("PARSING_ERROR", "structures experienced `pr.proteins.pdbfile.PDBParseError` when parsing PDB/mmCIF "
                                 "files."),
               ("PARSING_ERROR_OSERROR", "structures experienced OSErrors when parsing PDB/mmCIF files."),
               ("UNKNOWN_EXCEPTIONS", "structures experienced Unknown exceptions when parsing PDB/mmCIF files."),
               ("MISSING_ATOMS_ERROR", "structures failed because they had missing atoms."),
               ("NONE_STRUCTURE_ERRORS", "structures were returned as None from subroutine."),
               ("NONE_CHAINS", "chains became none when parsing."),
               ("COORDSET_INDEX_ERROR", "structures failed to correctly select ACSIndex.")]


class ProteinErrors(object):
    """
    A simple, flexible class to record and report errors when parsing.

    For each type of error, this class records the error's name (a short, descriptive title),
    the error's description, and an integer error code.

    The reason for implementing this extra class is that when using multiprocessing to process all the structures,
    the processes are free to fail by raising any type of special exception.  To communicate this information back
    to the parent process, we create a simple mapping from error to code/description so that these can be shown to
    the user.
    """
    def __init__(self):
        self.name_to_code = {}
        self.name_to_descr = {}
        self.counts = None
        for i, (error_name, error_descr) in enumerate(ERROR_CODES):
            self.name_to_code[error_name] = i
            self.name_to_descr[error_name] = error_descr

    def __getitem__(self, error_name):
        """ Returns the error code for a certain error name. """
        return self.name_to_code[error_name]

    def count(self, ec, pnid):
        """ Creates a record of a certain PNID exhibiting a certain error. """
        if not self.counts:
            self.counts = {ec: [] for ec in self.name_to_code.values()}

        self.counts[ec].append(pnid)

    def summarize(self):
        """ Prints a summary of all errors that have been recorded."""
        if not self.counts:
            print("Errors have not been accounted for.")
            return

        print("\nThe following errors occurred:")
        self.error_codes_inv = {v: k for k, v in self.name_to_code.items()}
        for error_code, count_list in self.counts.items():
            if len(count_list) > 0:
                name = self.error_codes_inv[error_code]
                descr = self.name_to_descr[name]
                print(f"{name + ':':<25}{len(count_list):^8}{descr}")
        print("")
        self.write_summary_files()

    def get_pnids_with_error_name(self, error_name):
        """ After counting, returns a list of pnids that have failed with a specified error code. """
        error_code = self[error_name]
        return self.counts[error_code]

    def get_error_names(self):
        """ Returns a list of error names. """
        return self.name_to_code.keys()

    def write_summary_files(self):
        """ For all counted errors, writes the list of pnids with each error to the errors/ directory. """
        os.makedirs("errors/", exist_ok=True)
        for e in self.get_error_names():
            if len(self.get_pnids_with_error_name(e)) > 0:
                with open(f"errors/{e}.txt", "w") as f:
                    f.write("\n".join(self.get_pnids_with_error_name(e)) + "\n")

ERRORS = ProteinErrors()
