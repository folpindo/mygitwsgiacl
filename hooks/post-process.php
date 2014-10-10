#! /usr/bin/php
<?php

try {

    define('JENKINS_SERVER', "http://jenkins:8080/");
    define('JENKINS_USER', "jenkins-post-commit-builder");
    define('JENKINS_PASS', "buildmyapp87");

    $GLOBALS['rev'] = array_search('--rev', $argv);
    $GLOBALS['repos'] = array_search('--repos', $argv);
    $GLOBALS['uuid'] = array_search('--uuid', $argv);
    $GLOBALS['author'] = array_search('--author', $argv);
    $GLOBALS['vcs'] = array_search('--vcs', $argv);
    $GLOBALS['ref'] = array_search('--ref', $argv);

    if (!$GLOBALS['vcs']) {
        throw new Exception("No Version Control System type passed. --vcs ['svn|git']");
    }
    $GLOBALS['vcs'] = $argv[$GLOBALS['vcs']+1];

    if ($GLOBALS['vcs'] == 'svn' && (!$GLOBALS['rev'] || !$GLOBALS['repos'])) {
        throw new Exception("SVN >> It's either the revision number or the "
                . "repository path is not passed on post-process.php hook.\n");
    }

    if ($GLOBALS['vcs'] == 'git' && !$GLOBALS['ref']) {
        throw new Exception("GIT >> Ref changes was not passed on post-process.php hook.\n");
    }

    $GLOBALS['rev'] = $argv[$GLOBALS['rev']+1];
    $GLOBALS['repos'] = $argv[$GLOBALS['repos']+1];
    $GLOBALS['pwd'] = realpath(dirname(__FILE__));
    $GLOBALS['author'] = $argv[$GLOBALS['author']+1];

    if ($GLOBALS['vcs'] == 'svn') {
        $GLOBALS['base_repo_dir'] = trim(strtolower(basename($GLOBALS['repos'])));
    } else {
        $GLOBALS['base_repo_dir'] = trim(strtolower($GLOBALS['repos']));
        $GLOBALS['ref'] = $argv[$GLOBALS['ref']+1];
    }
    $confJsonRepo = "{$GLOBALS['pwd']}/configs/json/{$GLOBALS['vcs']}/{$GLOBALS['base_repo_dir']}.json";

    $projConfig = importJsonFile($confJsonRepo);

    if (isset($projConfig) && count($projConfig) > 0) {
        $validBuildUsers = getJenkinsBuildUsers($projConfig);
        if (isset($validBuildUsers) && count($validBuildUsers) > 0) {
            if ((isset($projConfig['jenkins']['repo'][$GLOBALS['base_repo_dir']])
                && count($projConfig['jenkins']['repo'][$GLOBALS['base_repo_dir']]) > 0)
                && ($GLOBALS['base_repo_dir'] != "" && $GLOBALS['base_repo_dir'] != null))
            {
                if ($GLOBALS['author'] != "" && in_array($GLOBALS['author'], $validBuildUsers)) {

                    if ($GLOBALS['vcs'] == 'svn') {
	                runSvn($projConfig, $validBuildUsers);
                    } elseif ($GLOBALS['vcs'] == 'git') {
                        runGit($projConfig, $validBuildUsers);
                    }
                }
            }
        }
    }
} catch (Exception $e) {
    echo $e->getMessage();
    exit();
}

function runSvn($projConfig, $validBuildUsers)
{
    $stdIn = @file_get_contents('php://stdin', 'r');
    if ($stdIn) {
        $stdInArray = array_filter(array_map('trim', explode("\n", $stdIn)), 'strlen');
        if (count($stdInArray) > 0) {
            projectAnalyzer($projConfig, $stdInArray);
        }
    }
    unset($stdIn);
}

function runGit($projConfig, $validBuildUsers)
{
    $projBase = $projConfig['jenkins']['repo'][$GLOBALS['base_repo_dir']];

    if (isset($projBase[$GLOBALS['ref']])) {
        $job = $projBase[$GLOBALS['ref']]["job_name"];
        $authToken = $projBase[$GLOBALS['ref']]["auth_token"];
        triggerBuild($job, $authToken);
    }
}

function importJsonFile($pathFile)
{
    if (file_exists($pathFile) && is_readable($pathFile)) {
        $importData = @file_get_contents($pathFile);
        $data = @json_decode($importData, true);
        if (empty($data)) {
            return array();
        }

        return $data;
    }

    return array();
}

function getJenkinsBuildUsers($projConfig)
{
    $projBuildUsers = array(); $baseBuildUsers = array();
    if (isset($projConfig['jenkins']['groups']['jbuilders'])
        && count($projConfig['jenkins']['groups']['jbuilders']) > 0)
    {
        $projBuildUsers = $projConfig['jenkins']['groups']['jbuilders'];
    }
    $confBaseGrp= $GLOBALS['pwd'] . "/configs/json/groups.json";

    $baseGroup = importJsonFile($confBaseGrp);
    if (isset($baseGroup['jbuilders']) && count($baseGroup['jbuilders']) > 0) {
        $baseBuildUsers = $baseGroup['jbuilders'];
    }
    $buildUsers = array_merge($baseBuildUsers, $projBuildUsers);

    return $buildUsers;
}

function projectAnalyzer($projConfig, $stdInArray = array())
{
    $projBase = $projConfig['jenkins']['repo'][$GLOBALS['base_repo_dir']];
    $baseRepoProj = array_keys($projBase);

    foreach ($baseRepoProj as $subRepo) {
        if (count($stdInArray) > 0) {
            $varme = addcslashes("$subRepo","/");
            $grepResult = preg_grep("/^$varme/", $stdInArray);
            if ($grepResult) {
                $job = $projBase[$subRepo]["job_name"];
                $authToken = $projBase[$subRepo]["auth_token"];
                triggerBuild($job, $authToken);

                //optimization on the next grep
                //this will return the remaining stdin result
                $stdInArray = array_diff($stdInArray, $grepResult);
            }
        } else {
            break;
        }
    }
}

function triggerBuild($job, $authToken)
{
    $execWget = "/usr/bin/wget "
        . "--auth-no-challenge "
        . "--no-check-certificate "
        . "--quiet "
        . "--no-cookies "
        . "--http-user=" . JENKINS_USER
        . " --http-password=" . JENKINS_PASS
        . " --header 'Content-Type:text/plain;charset=UTF-8' "
        . "--post-data 'token={$authToken}' "
        . "--output-document '-' "
        . "--timeout=2 " . JENKINS_SERVER . "/job/$job/build";
    @exec($execWget);
}

//debugger
//@file_put_contents("$pwd/test.tmp", $author, LOCK_EX);
