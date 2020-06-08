import sublime, sublime_plugin
import re
import os

from Default import history_list


COMMON_PATHS = {
    "to"          : "std.conv",
    "writeln"     : "std.stdio",
    "writefln"    : "std.stdio",
    "format"      : "std.format",
    "rint"        : "std.math",
    "cos"         : "std.math",
    "sin"         : "std.math",
    "tan"         : "std.math",
    "PI"          : "std.math",
    "PI_2"        : "std.math",
    "abs"         : "std.math",
    "fabs"        : "std.math",
    "sqrt"        : "std.math",
    "ceil"        : "std.math",
    "floor"       : "std.math",
    "round"       : "std.math",
    "trunc"       : "std.math",
    "lrint"       : "std.math",
    "nearbyint"   : "std.math",
    "rndtol"      : "std.math",
    "quantize"    : "std.math",
    "isNaN"       : "std.math",
    "find"        : "std.algorithm.searching",
    "canFind"     : "std.algorithm.searching",
    "until"       : "std.algorithm.searching",
    "count"       : "std.algorithm.searching",
    "countUntil"  : "std.algorithm.searching",
    "GC"          : "core.memory",
    "thisExePath" : "std.file",
}


def _find_common_path( symbol ):
    base_path = COMMON_PATHS.get( symbol, None )

    if base_path:
        return base_path

    return "std."


def _get_module_name_from_abs_path( abs_path ):
    import os.path

    # remove ext
    abs_path, ext = os.path.splitext( abs_path )

    # trim.  project/source/ui/event to ui/event
    folders = []
    folder_path, folder = os.path.split( abs_path )

    while ( folder_path and folder ):
        if folder == "source" or folder == "src":
            break

        folders.insert( 0, folder )
        folder_path, folder = os.path.split( folder_path )

    return ".".join( folders )


def _get_module_name( file_name ):
    with open( file_name ) as f:
        for i, line in enumerate( f ):
            if i > 10:
                break

            if line.startswith( "module " ):
                module_name = line
                module_name = line[ len( "module " ): ]
                module_name = module_name.rstrip( "\n" ).strip( " " ).rstrip( ";" ).rstrip( " " )
                return module_name

    return  _get_module_name_from_abs_path( file_name )


class DlangAutoImportReplaceTextCommand( sublime_plugin.TextCommand ):
    def run( self, edit, region, text ):
        region = sublime.Region( *region )
        self.view.replace( edit, region, text )


class DlangAutoImportCommand( sublime_plugin.TextCommand ):
    def is_visible( self ):
        return self.view.match_selector( 0, "source.d" )


    def _lookup_symbol( self, edit, symbol ):
        locs = self.view.window().lookup_symbol_in_index( symbol )
        locs = [ l for l in locs if l[ 1 ].endswith(".d") or l[ 1 ].endswith(".di") ]
        
        # Unique
        uniqued_locs = []
        for l in locs:
            unique = True
            for ul in uniqued_locs:
                if ul[ 0 ] == l[ 0 ]: # test abs path
                    unique = False
                    break
            if unique:
                uniqued_locs.append( l )

        locs = uniqued_locs

        # Get
        if len( locs ) == 1:
            abs_path = locs[ 0 ][ 0 ]
            import_path = _get_module_name( abs_path )
            return import_path
        
        elif len( locs ) > 1:
            self._select_location_via_menu( edit, locs, symbol )

        else:
            import_path = _find_common_path( symbol )
            return import_path


    def _select_location_via_menu( self, edit, locs, symbol ):

        items = [ l[ 1 ]  for l in locs ]
        self._preview = None

        def on_done( item_index ):
            print( self._preview )
            if self._preview is not None:
                self.view.window().focus_view( self._preview ) 
                self.view.window().run_command( "close_file" )
                self.view.window().focus_view( self.view )

            if item_index != -1:
                abs_path = locs[ item_index ][ 0 ]
                import_path = _get_module_name( abs_path )

                self._insert( edit, import_path, symbol )

        def on_highlighted( item_index ):
            item = locs[ item_index ]
            abs_path = item[ 0 ]
            location = item[ 2 ]
            r = location[ 0 ]
            c = location[ 1 ]
            abs_path_encoded = "{}:{}:{}".format( abs_path, r, c )
            self._preview = self.view.window().open_file( abs_path_encoded, sublime.ENCODED_POSITION | sublime.TRANSIENT )
            self._preview.set_scratch( True )


        self.view.show_popup_menu( items, on_done, 0 )
        # self.view.window().show_quick_panel( items, on_done, 0, 0, on_highlighted )
        # self.view.window().show_quick_panel( items, on_done, 0, 0 )



    def _check_exists( self, edit, symbol ):
        # check "import ... : <Symbol> ;"
        query = "^import .*:.*[ ,;]+{}[ ,;].*".format( symbol )

        use_statements = self.view.find_all( query )

        if len( use_statements ) > 0:
            return use_statements[ 0 ].b


    def _inside_import( self, edit, import_path, symbol ):
        # inside "import ... : <Symbol> ;"
        query = "^import {}[ ]*:[ ]*[.]+;$".format( import_path )

        use_statements = self.view.find_all( query )

        if len( use_statements ) > 0:
            insert_point = use_statements[ 0 ].b - 2
            new_import = ", {}".format( symbol )

            self._safe_insert( insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _afrer_imports( self, edit, import_path, symbol ):
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

            self._safe_insert( insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _afrer_module( self, edit, import_path, symbol ):
        # after "module ..."
        query = "^module .+;$"
        use_statements = self.view.find_all(query)

        if len( use_statements ) > 0:
            use_start = use_statements[ 0 ].a
            r, c = self.view.rowcol( use_start )

            insert_point = self.view.text_point( r + 1, c )
            new_import = "\nimport {} : {};\n".format( import_path, symbol )

            self._safe_insert( insert_point, new_import )

            return insert_point + len( new_import ) - 1


    def _at_top( self, edit, import_path, symbol ):
        # at top in file
        new_import = "import {} : {};\n".format( import_path, symbol )

        self._safe_insert( 0, new_import )

        return len( new_import ) - 1


    def _select( self, edit, sel_i ):
        sel = self.view.sel()
        sel.clear()
        sel.add( sublime.Region( sel_i, sel_i ) )

        # scroll t show it
        self.view.show( sel_i )


    def _safe_insert( self, insert_point, new_import ):
        self.view.run_command( 'dlang_auto_import_replace_text', { "region": [insert_point, insert_point], "text": new_import } )


    def _insert( self, edit, import_path, symbol ):
        inserted = self._inside_import( edit, import_path, symbol )
    
        if inserted is None:
            inserted = self._afrer_imports( edit, import_path, symbol )

        if inserted is None:
            inserted = self._afrer_module( edit, import_path, symbol )

        if inserted is None:
            inserted = self._at_top( edit, import_path, symbol )

        # Select inserted
        if inserted is not None:
            self._select( edit, inserted )


    def run(self, edit, **args):
        history_list.get_jump_history_for_view(self.view).push_selection(self.view)
        symbol = self.view.substr(self.view.word(self.view.sel()[0]))

        # Check 
        exist_point = self._check_exists( edit, symbol )
        if exist_point:
            self._select( edit, exist_point )
            return

        # Lookup for <Symbol>
        import_path = self._lookup_symbol( edit, symbol )

        # Get insert point
        if import_path:
            self._insert( edit, import_path, symbol )
