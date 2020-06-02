import sublime, sublime_plugin
import re
import os

from Default import history_list


COMMON_PATHS = {
    "to": "std.conv",
}


def find_common_path( symbol ):
    base_path = COMMON_PATHS.get( symbol, None )

    if base_path:
        return base_path

    return "std."


def matchiness( a, b ):
    m = 0
    for sa, sb in zip(a,b):
        if sa != sb:
            return m
        m += 1
    return m


def get_module_name_from_abs_path( abs_path ):
    import os.path

    folders = []
    folder_path, folder = os.path.split( abs_path )

    while ( folder_path and folder ):
        if folder == "source" or folder == "src":
            break

        folders.insert(  folder )
        folder_path, folder = os.path.split( folder_path )

    return folders.join( "." )


def get_module_name( file_name ):
    with open( file_name ) as f:
        for i, line in enumerate( f ):
            if i > 10:
                break

            if line.startswith( "module " ):
                module_name = line
                module_name = line[ len( "module " ): ]
                module_name = module_name.rstrip( "\n" ).rstrip( " " ).rstrip( ";" ).rstrip( " " )
                return module_name

    return get_module_name_from_file_name( file_name )


class DlangAutoImportCommand(sublime_plugin.TextCommand):
    def _check_exists( self, edit, symbol ):
        # check "import ... : <Symbol> ;"
        query = "^import .*:.*[ ,;]+{}[ ,;].*".format( symbol )

        use_statements = self.view.find_all( query )

        if len( use_statements ) > 0:
            return use_statements[ 0 ].b


    def _inside_import( self, import_path, edit, symbol ):
        # inside "import ... : <Symbol> ;"
        query = "^import {}[ ]*:[ ]*[.]+;$".format( import_path )

        use_statements = self.view.find_all( query )

        if len( use_statements ) > 0:
            insert_point = use_statements[ 0 ].b - 2
            new_import = ", {}".format( symbol )

            self.view.insert( edit, insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _afrer_imports( self, import_path, edit, symbol ):
        # after "import ... ;"
        query = "^import .+"
        use_statements = self.view.find_all( query )

        if len( use_statements ) > 0:
            # get last "import ..."
            last_import_r = 0

            for use_statement in use_statements:
                r, c = self.view.rowcol( use_statement.a )

                # in fitst 100 lines 
                if r > 100:
                    break

                last_import_r = r

            # multylibe 
            # "import ...,
            #         ...;"
            insert_point = self.view.text_point( last_import_r, 0 )
            line = self.view.substr( self.view.line( insert_point ) )
            if line.rstrip().endswith( "," ):
                insert_point = self.view.text_point( last_import_r, 0 )
            else:
                insert_point = self.view.text_point( last_import_r + 1, 0 )

            new_import = "import {} : {};\n".format( import_path, symbol )

            self.view.insert( edit, insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _afrer_module( self, import_path, edit, symbol ):
        # after "module ..."
        query = "^module .+;$"
        use_statements = self.view.find_all(query)

        if len( use_statements ) > 0:
            use_start = use_statements[ 0 ].a
            r, c = self.view.rowcol( use_start )

            insert_point = self.view.text_point( r + 1, c )
            new_import = "\nimport {} : {};\n".format( import_path, symbol )

            self.view.insert( edit, insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _at_top( self, import_path, edit, symbol ):
        # at top in file
        new_import = "import {} : {};\n".format( import_path, symbol )

        self.view.insert( edit, 0, new_import )

        return len( new_import ) - 1


    def run(self, edit, **args):
        history_list.get_jump_history_for_view(self.view).push_selection(self.view)
        symbol = self.view.substr(self.view.word(self.view.sel()[0]))

        # Check 
        exist_point = self._check_exists( edit, symbol )
        if exist_point:
            sel_i = exist_point
            sel = self.view.sel()
            sel.clear()
            sel.add( sublime.Region( sel_i, sel_i ) )

            # scroll t show it
            self.view.show( sel_i )

            return

        # Lookup for <Symbol>
        locs = self.view.window().lookup_symbol_in_index( symbol )
        locs = [ l for l in locs if l[ 1 ].endswith(".d") or l[ 1 ].endswith(".di") ]

        if len( locs ) > 0:
            abs_path = locs[ 0 ][ 0 ]
            module_name = get_module_name( abs_path )
            import_path = module_name

        else:
            import_path = find_common_path( symbol )

        # Get insert point
        if import_path:
            inserted = self._inside_import( import_path, edit, symbol )
        
            if inserted is None:
                inserted = self._afrer_imports( import_path, edit, symbol )

            if inserted is None:
                inserted = self._afrer_module( import_path, edit, symbol )

            if inserted is None:
                inserted = self._at_top( import_path, edit, symbol )

            # Select inserted
            if inserted is not None:
                sel_i = inserted
                sel = self.view.sel()
                sel.clear()
                sel.add( sublime.Region( sel_i, sel_i ) )

                # scroll. show
                self.view.show( sel_i )
