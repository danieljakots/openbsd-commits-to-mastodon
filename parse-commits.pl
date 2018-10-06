#!/usr/bin/perl
########################################################################
# Copyright (c) 2012 Andrew Fresh <andrew@afresh1.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
########################################################################
use strict;
use warnings;
use 5.012;
use Encode qw(encode decode);

my $default_maxlen = 280;

my %accounts = (
    cvs      => 'openbsd_cvs',
    src      => 'openbsd_src',
    ports    => 'openbsd_ports',
    xenocara => 'openbsd_xenocara',
    www      => 'openbsd_www',
    stable   => 'openbsd_stable',

    sets    => 'openbsd_sets',
);



my ($changelog) = @ARGV;
die "Usage: $0 <path/to/ChangeLog>\n" unless $changelog;

my @commits = parse_changelog($changelog);
foreach my $details (@commits) {
    #print( $details )."\n";
    check_message( $details );
}


sub check_message {
    my ($details) = @_;

    return unless $details;
    return unless $details->{id};

    my ( $message, $params ) = make_tweet($details);
    tweet( $message, $params )
}


sub tweet {
    my ( $message, $params ) = @_;

    #say( $params->{who} )
    print $params->{who}. " ";
    say encode('UTF-8', "$message");
    #foreach (sort keys %params) {
    #    print "$_ : $params{$_}\n";
    #}
    #my $encoded = encode('UTF-8', $message);
}


sub change_for {
    my ($commit) = @_;
    my %changes;
    my @dirs;

    my $has_regress     = 0;
    my $has_non_regress = 0;
    foreach my $key ( keys %{$commit} ) {
        if ( $key =~ /^(\w+)\s+files$/ ) {
            $changes{ lc $1 }++;
            foreach ( keys %{ $commit->{$key} } ) {
                my $dir = $_;
                my @files = @{ $commit->{$key}->{$dir} || [] };
                @files = '' unless @files;

                if   ( $dir =~ s{^regress/}{} ) { $has_regress++ }
                else                            { $has_non_regress++ }

                push @dirs, map {"$dir/$_"} @files;
            }
        }
    }

    my @changes = keys %changes;
    my $changed = @changes == 1 ? $changes[0] : 'changed';

    unless (@dirs) {
        if (@changes) {
            return "$changed something";
        }
        return "did something the parser didn't understand";
    }

    # Put them shortest first
    @dirs = sort { length $a <=> length $b } @dirs;
    my $num_changed = @dirs;

    my $match = shift @dirs;
    $match //= '';

    my $last = '/';
    foreach my $dir (@dirs) {
        $last = chop $match while $dir !~ /^\Q$match/;
    }
    $match .= '*' if $match and $last ne '/' and $match !~ m{/$};

    $match =~ s{^[\.\/]+}{};    # No need for leading ./
    $match =~ s{/+$}{};         # one less char most likely

    my $message = $changed;
    if ( !$match ) {
        if ($has_non_regress) {
            if    ( $num_changed > 5 ) { $message .= ' many things' }
            elsif ( $num_changed > 2 ) { $message .= ' a few things' }
            elsif ( $num_changed > 1 ) { $message .= ' a couple things' }
            else                       { $message .= ' something' }
        }
        $message .= ' including' if $has_regress and $has_non_regress;
        $message .= ' regression tests' if $has_regress;
    }
    elsif ($has_regress) {
        if ($has_non_regress) {
            $message .= " $match and regression tests";
        }
        else {
            $message .= " regress/$match";
        }
    }
    else {
        $message .= " $match";
    }

    return $message;
}

sub parse_changelog {
    my ($file) = @_;
    return {} unless -f $file;

    my @commits;
    my %commit;

    my $finish_commit = sub {
        if ( my $changes = $commit{'Changes by'} ) {
            my ( $who, $when ) = split /\s+/, $changes, 2;
            $commit{'Changes by'} = $who;
            $commit{'Changes on'} = $when;
        }

        $commit{'Log message'} //= '';
        $commit{'Log message'} =~ s/^\s+//gm;
        $commit{'Log message'} =~ s/\s+$//gm;

        $commit{id} = join '|', grep {defined}
            @commit{ 'Module name', 'Changes by', 'Changes on' };

        push @commits, {%commit};
        %commit = ();
    };

    open my $fh, '<', $file or die $!;
    my $key = '';
    my $dir = '';
    while (1) {
        $_ = decode('UTF-8', readline $fh) || last;
        chomp;

        if (/^\s*(CVSROOT|Module name|Changes by):\s+(.*)$/) {
            $commit{$1} = $2;
            next;
        }
        next unless $commit{CVSROOT};    # first thing should be CVSROOT

        if (/^(Update of)\s+(.*)\/([^\/]+)$/) {
            $commit{'Updated files'}{$2} = [$3];
            next;
        }

        if (/^(\w+ files):/) {
            $key = $1;
            next;
        }

        if ($key) {
            s/^\s+//;
            unless ($_) { $key = ''; $dir = ''; next; }

            my @files;
            if (/^\s*([^:]*?)\s*:\s*(.*)$/) {
                $dir = $1;
                @files = $2;
            }
            else { @files = $_ }
            @files = map {split} @files;
            next unless $dir;

            if (@files && $files[0] eq 'Tag:') {
                my $k = shift @files;
                my $v = shift @files;

                $k =~ s/:$//;
                $commit{$k} = $v;
            }

            push @{ $commit{$key}{$dir} }, @files;
            next;
        }

        if (/^Log [Mm]essage:/) {
            my $cvsroot = parse_log_message( \%commit, $fh );
            $finish_commit->();
            $commit{CVSROOT} = $cvsroot;
        }
    }
    close $fh;

    $finish_commit->();
    return @commits;
}

sub parse_log_message {
    my ( $commit, $fh ) = @_;

    my $importing = 0;

    while (<$fh>) {
        if ( /^CVSROOT:\s+(.*)$/ ) {
            return $1; # we've found the end of this message
        }
        elsif ( my ( $k, $v ) = /^\s*(Vendor Tag|Release Tags):\s+(.*)$/ ) {
            $commit->{$k} = $v;
            $commit->{'Log message'} =~ s/\s*Status:\s*$//ms;
            $importing = 1;
        }
        elsif ( $importing && m{^\s*[UCN]\s+[^/]*/(.*)/([^/]+)\b$} ) {
            push @{ $commit->{'Imported files'}{$1} }, $2;
        }
        else {
            $commit->{'Log message'} .= $_;
        }
    }
    return;
}

sub account_for {
    my ($module) = @_;
    return $accounts{$module} || 'openbsd_cvs';
}

sub shorten {
    my ($message, $maxlen) = @_;
    $maxlen ||= $default_maxlen;
    if ( length $message > $maxlen ) {
        my $keep = $maxlen - 3;
        $message =~ s/^(.{$keep}).*/$1/ms;
        $message =~ s/\s+$//ms;
        $message .= '...';
    }
    return $message;
}


sub make_tweet {
    my ($commit) = @_;
    #return make_tweet_for_sets($commit) if $commit->{type};

    my %params = ( who => account_for( $commit->{'Module name'} ), );

    my $by = $commit->{'Changes by'};
    $by =~ s/\@.*$/\@/;

    my $change = change_for($commit);

    my $message = "$by $change: " . $commit->{'Log message'};
    $message = $commit->{Tag} . ' ' . $message if $commit->{Tag};
    $message =~ s/\s*\d+\s*conflicts created by this import.*//s;
    $message =~ s/\s+/ /gms;

    #say shorten($message), \%params;
    return shorten($message), \%params;
}

